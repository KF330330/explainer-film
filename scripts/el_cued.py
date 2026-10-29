#!/usr/bin/env python3
"""ElevenLabs 逐 cue 配音（只用标准库＋ffmpeg/ffprobe）：make_audio.py、approve_voice.py 经 project.json 的 voice.elevenlabs.tts_cued 调它（null＝本文件）。

每条 cue 单独送 ElevenLabs 合成，各段统一解码成单声道 s16le PCM，按样本数精确算 cue 起止、插入气口静音，拼接后一次编码成 MP3。
用法：el_cued.py <spec.json> <out_dir>
输入 spec：{"slug", "provider": "elevenlabs"（必须，否则退出 2）, "silence_gap_ms": 150, "style", "sample_rate": 32000, "bitrate": 128000,
           "cues": [{"id", "text", "force_regenerate"?: true}]}；content_type 等其余键忽略。
环境变量：ELEVENLABS_TTS_VOICE_ID（必须，20 位字母数字）；密钥先看 ELEVENLABS_API_KEY，没有就读 ~/.config/elevenlabs/api-key
          （目录须本人所有且组与其他人不可写，文件须本人所有、权限 600）；EF_ELEVENLABS_API_BASE 覆盖接口地址，只供测试用。
气口：cue 之间默认 silence_gap_ms；读法稿以句末标点结尾抬到 ≥450 ms，问号结尾 ≥550 ms（句末标点后可跟右引号）。
缓存：<out_dir>/cache/<键>.mp3＋同名 .json；键＝{"schema":1, voice_fp: sha256(voice_id)[:12], model, styled_text, voice_settings, output_format,
      sample_rate, bitrate} 的 sha256。命中且 sha256 对得上就不发请求；force_regenerate 时必发。
输出：<out_dir>/<slug>.mp3 与 <slug>.cues.json（样本级 start/end、每条的 generation{provider, model, request_id, request_cache_hit}）；
      两个文件都先在临时目录写好再 os.replace 发布，失败不留半截；cues.json 不写 voice ID 原文。
退出码：0 成功；2 spec、配置或缺 ffmpeg/ffprobe；1 合成或编码失败。
"""
from __future__ import annotations
import fcntl
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True   # 不在 skill 目录里写 __pycache__

# ---------------- ElevenLabs 接口（照抄 elevenlabs_tts.py） ----------------
API_BASE = (os.environ.get("EF_ELEVENLABS_API_BASE") or "https://api.elevenlabs.io/v1/text-to-speech").rstrip("/") + "/"
MODEL = "eleven_v4"
VOICE_ID = ""  # set ELEVENLABS_TTS_VOICE_ID or pass voice_id
KEY_FILE = Path.home() / ".config/elevenlabs/api-key"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75}
MAX_CHARACTERS = 10000  # V4 per-request text ceiling, not a credit/quota cap.

class ElevenLabsHardError(RuntimeError):
    """Unknown completion, refusal or invalid output: never replay."""

class ElevenLabsUnavailableError(RuntimeError):
    """Definite pre-audio unavailability (missing key, 401/402/404/429)."""

def resolve_key():
    value = os.getenv("ELEVENLABS_API_KEY")
    if value:
        value = value.strip()
        if not value or len(value) > 16384 or any(c.isspace() for c in value):
            raise ElevenLabsHardError("elevenlabs_environment_key_invalid")
        return value
    try:
        parent = KEY_FILE.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
            raise ElevenLabsHardError("elevenlabs_private_directory_permissions_invalid")
        fd = os.open(KEY_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ElevenLabsHardError("elevenlabs_private_key_permissions_invalid")
            value = stream.read(16385).strip()
            if not value or len(value) > 16384 or any(c.isspace() for c in value):
                raise ElevenLabsHardError("elevenlabs_private_key_invalid")
            return value
    except FileNotFoundError:
        raise ElevenLabsUnavailableError("elevenlabs_api_key_missing") from None
    except (OSError, UnicodeError):
        raise ElevenLabsHardError("elevenlabs_private_key_unreadable") from None

def resolve_voice(voice_id=None):
    value = voice_id or os.getenv("ELEVENLABS_TTS_VOICE_ID") or VOICE_ID
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{20}", value):
        raise ValueError("ElevenLabs requires a verified 20-character voice ID")
    return value

def validate_tags(audio_tags):
    if audio_tags is None:
        return []
    if not isinstance(audio_tags, list):
        raise ValueError("audio_tags must be a list")
    result = []
    for entry in audio_tags:
        if not isinstance(entry, dict) or set(entry) != {"before", "tag"}:
            raise ValueError("Each audio tag requires only before and tag")
        before, tag = entry["before"], entry["tag"]
        if not isinstance(before, str) or not isinstance(tag, str) or not tag.strip() or len(tag) > 200:
            raise ValueError("Invalid audio tag or anchor")
        if before and not before.strip():
            raise ValueError("Nonempty audio tag anchors must not be whitespace-only")
        if any(c in tag for c in "[]") or any(ord(c) < 32 or ord(c) == 127 for c in tag):
            raise ValueError("Audio tags must be plain one-line delivery directions")
        result.append({"before": before, "tag": tag.strip()})
    return result

def styled_text(text, style, audio_tags=None):
    # Brackets in source prose are ambiguous controls. Use separate structured tags.
    if "[" in text or "]" in text:
        raise ValueError("V4 source prose must not contain square brackets; use audio_tags")
    entries = validate_tags(audio_tags)
    if style:
        validate_tags([{"before": "", "tag": style}])
    placements = []
    for entry in entries:
        anchor = entry["before"]
        if anchor and text.count(anchor) != 1:
            raise ValueError("V4 audio tag anchor must match once in normalized spoken text")
        placements.append((text.index(anchor) if anchor else 0, "[" + entry["tag"] + "] "))
    if style:
        placements.insert(0, (0, "[" + style.strip() + "] "))
    # Stable order for multiple tags at the same position; never rewrite prose.
    for _, (position, direction) in sorted(enumerate(placements), key=lambda item: (item[1][0], item[0]), reverse=True):
        text = text[:position] + direction + text[position:]
    if len(text) > MAX_CHARACTERS:
        raise ValueError("V4 request exceeds 10000 characters; split into complete semantic cues")
    return text

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _open(request, timeout):
    return urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)

def _request(text, voice_id, timeout, key):
    payload = dict(text=text, model_id=MODEL, voice_settings=VOICE_SETTINGS)
    req = urllib.request.Request(API_BASE + resolve_voice(voice_id) + "?output_format=" + OUTPUT_FORMAT,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}, method="POST")
    for attempt in range(3):
        try:
            with _open(req, timeout) as response:
                data = response.read()
                length = response.headers.get("Content-Length")
                if length is not None and len(data) != int(length):
                    raise ElevenLabsHardError("elevenlabs_response_length_mismatch")
                if "audio" not in response.headers.get("Content-Type", "").lower() or not data or not (
                        data.startswith(b"ID3") or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224)):
                    raise ElevenLabsHardError("elevenlabs_invalid_or_empty_audio")
                request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
                if request_id and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", request_id):
                    request_id = None
                cost = response.headers.get("character-cost")
                if cost and not re.fullmatch(r"[0-9]+(?:[.][0-9]+)?", cost):
                    cost = None
                return data, dict(request_id=request_id, character_cost_header=cost,
                    attempts=attempt + 1, completion="http_body_complete")
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read(65536).decode("utf-8", errors="replace")
            except Exception:
                raise ElevenLabsHardError("elevenlabs_error_response_uncertain") from None
            try:
                detail = json.loads(body).get("detail", {})
                code = detail.get("status") if isinstance(detail, dict) else None
            except (ValueError, AttributeError):
                code = None
            if re.search(r"safety|moderation|policy|refus|blocked|prohibit|unsafe|content.filter", body, re.I):
                raise ElevenLabsHardError("elevenlabs_http_" + str(exc.code) + "_policy_or_blocked") from None
            if exc.code == 429 and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            if exc.code in (401, 402, 404, 429) or (exc.code == 403 and code == "missing_permissions"):
                raise ElevenLabsUnavailableError("elevenlabs_http_" + str(exc.code)) from None
            # A 5xx does not prove a POST did not consume credits. No blind replay.
            raise ElevenLabsHardError("elevenlabs_http_" + str(exc.code) + "_stopped") from None
        except (ElevenLabsHardError, ElevenLabsUnavailableError):
            raise
        except Exception:
            raise ElevenLabsHardError("elevenlabs_request_outcome_uncertain_may_have_billed") from None

def _measure(path, ffmpeg, ffprobe):
    try:
        probe = json.loads(subprocess.check_output([ffprobe, "-v", "error", "-show_entries",
            "format=duration:stream=codec_name,sample_rate,channels,bit_rate", "-of", "json", str(path)],
            stderr=subprocess.DEVNULL, text=True, timeout=30))
        duration = float(probe["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0 or len(probe["streams"]) != 1:
            raise ValueError("invalid audio")
        stream = probe["streams"][0]
        if stream["codec_name"] != "mp3":
            raise ValueError("Expected an MP3 audio stream")
        result = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-xerror", "-i", str(path),
            "-af", "ebur128=peak=true:framelog=verbose,volumedetect", "-f", "null", "-"],
            check=True, capture_output=True, text=True, timeout=60)
        peak = float(re.findall(r"Peak:\s+(-?[0-9.]+) dBFS", result.stderr)[-1])
        sample_peak = float(re.findall(r"max_volume:\s+(-?[0-9.]+) dB", result.stderr)[-1])
        return dict(duration=duration, sample_rate=int(stream["sample_rate"]),
            channels=stream["channels"], codec=stream["codec_name"], bitrate=int(stream.get("bit_rate", 0)),
            true_peak_db=peak, sample_peak_db=sample_peak)
    except Exception:
        raise ElevenLabsHardError("elevenlabs_audio_decode_or_measurement_failed") from None

def synthesize(text, style, voice_id, sample_rate, bitrate, volume, timeout, ffmpeg, ffprobe, audio_tags=None):
    tagged = styled_text(text, style, audio_tags)
    if sample_rate not in {8000,11025,12000,16000,22050,24000,32000,44100,48000} or bitrate not in {
        8000,16000,24000,32000,40000,48000,56000,64000,80000,96000,112000,128000,144000,160000,192000,224000,256000,320000}:
        raise ValueError("Invalid MP3 sample rate or bitrate")
    key = resolve_key()
    if not ffmpeg or not ffprobe:
        raise ElevenLabsUnavailableError("elevenlabs_media_tools_missing")
    started = time.monotonic()
    native, receipt = _request(tagged, voice_id, timeout, key)
    with tempfile.TemporaryDirectory(prefix="elevenlabs-tts-") as folder:
        original, output = Path(folder) / "native.mp3", Path(folder) / "speech.mp3"
        original.write_bytes(native)
        native_probe = final_probe = _measure(original, ffmpeg, ffprobe)
        reencoded = not (sample_rate == native_probe["sample_rate"] and bitrate == native_probe["bitrate"]
            and native_probe["channels"] == 1 and volume == 1 and
            max(native_probe["true_peak_db"], native_probe["sample_peak_db"]) <= -1)
        gain_db = 20 * math.log10(volume)
        audio = native
        if reencoded:
            peak = max(native_probe["true_peak_db"], native_probe["sample_peak_db"])
            gain_db = min(gain_db, -2 - peak)
            for _ in range(2):
                try:
                    subprocess.run([ffmpeg, "-v", "error", "-xerror", "-y", "-i", str(original),
                        "-af", "volume=" + str(gain_db) + "dB", "-ar", str(sample_rate), "-ac", "1",
                        "-b:a", str(bitrate), str(output)], check=True, capture_output=True, timeout=60)
                except Exception:
                    raise ElevenLabsHardError("elevenlabs_generated_audio_encoding_failed") from None
                final_probe = _measure(output, ffmpeg, ffprobe)
                final_peak = max(final_probe["true_peak_db"], final_probe["sample_peak_db"])
                if final_peak <= -1:
                    audio = output.read_bytes()
                    break
                gain_db += -2 - final_peak
            else:
                raise ElevenLabsHardError("elevenlabs_encoded_audio_peak_unsafe")
    receipt.update(provider="elevenlabs", model=MODEL, voice_id=voice_id, voice_kind="cloned",
        output_format="mp3", native_output_format=OUTPUT_FORMAT, voice_settings=dict(VOICE_SETTINGS),
        sample_rate=sample_rate, style=style, style_applied=bool(style),
        audio_tags_requested=validate_tags(audio_tags), audio_tags_applied=bool(audio_tags),
        spoken_text_sha256=hashlib.sha256(tagged.encode()).hexdigest(),
        tempo_modified=False, reencoded=reencoded, requested_gain_db=20 * math.log10(volume), gain_db=gain_db if reencoded else 0,
        native_audio_sha256=hashlib.sha256(native).hexdigest(), sha256=hashlib.sha256(audio).hexdigest(),
        audio_probe=final_probe, processing_seconds=round(time.monotonic() - started, 3))
    return audio, receipt

# ---------------- 读法稿预处理（照抄 pronunciation.py 的 normalize_spoken_hyphens） ----------------
# Spoken-path dash class: ASCII hyphen, en dash U+2013, em dash U+2014,
# Unicode minus U+2212. Display/subtitle text is never rewritten here.
_SPOKEN_HYPHEN_BETWEEN_ALNUM = re.compile(
    r"(?<=[A-Za-z0-9])["
    + "-–—−"
    + r"](?=[A-Za-z0-9])"
)
# Between Latin alnum only: GPT-6.1 / always-on / Claude-Opus-4 → spaces.
# Does NOT match spaced pure-integer subtraction like "5 - 3" (no adjacent alnum).

def normalize_spoken_hyphens(text: str) -> str:
    """Turn speakable-unit hyphens into spaces before sending to TTS.

    - Version/model/product compounds with Latin letters/digits around a hyphen or
      en/em/minus dash → replace dash with a space (GPT-6.1 → GPT 6.1;
      Claude-Opus-4 → Claude Opus 4; always-on → always on). Class strategy, not
      a word list: any dash between [A-Za-z0-9] on both sides.
    - Idempotent: already-spaced GPT 6.1 unchanged.
    - Tradeoff: intentional numeric subtraction written tight as 5-3 becomes
      "5 3" (rare in narration). Spaced "5 - 3" is preserved.
    - Display/subtitle text stays separate — this runs on the spoken path only.
    """
    if not text:
        return text
    return _SPOKEN_HYPHEN_BETWEEN_ALNUM.sub(" ", text)

# ---------------- 气口与 PCM 拼接（照抄 tts_cued.py） ----------------
# Sentence-final silence floors.
SENTENCE_FLOOR_MS = 450
QUESTION_FLOOR_MS = 550
_CLOSING_AFTER_PUNCT = "”’」』】\""


def sentence_final_silence_floor_ms(text: str) -> int | None:
    """Return required inter-cue silence floor (ms) if text ends with sentence-final punct.

    Closing quotes after punct are ignored. Question marks use 550; other sentence-final
    use 450. Returns None if no sentence-final punct at end (caller keeps silence_gap_ms).
    """
    t = (text or "").rstrip()
    if not t:
        return None
    # Strip trailing closing quotes for classification after confirming punct-at-end.
    # Pattern: optional closing quotes after punct, optional trailing space already stripped.
    m = re.search(r"([。！？.!?])([" + re.escape(_CLOSING_AFTER_PUNCT) + r"]*)$", t)
    if not m:
        return None
    punct = m.group(1)
    if punct in ("？", "?"):
        return QUESTION_FLOOR_MS
    return SENTENCE_FLOOR_MS


def effective_inter_cue_gap_ms(cue_text: str, silence_gap_ms: int) -> int:
    """Inter-cue gap: raise silence_gap_ms to sentence-final floor when cue ends with punct."""
    floor = sentence_final_silence_floor_ms(cue_text)
    if floor is None:
        return int(silence_gap_ms)
    return max(int(silence_gap_ms), int(floor))


def ffprobe_duration(path: Path) -> float:
    """精确测量 mp3 时长（秒）。"""
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(out.decode().strip())


def decode_pcm(src: Path, dst: Path, sample_rate: int) -> int:
    """Normalize any supported fragment to mono signed 16-bit little-endian PCM."""
    subprocess.run([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(src),
        "-map", "0:a:0", "-vn", "-ar", str(sample_rate), "-ac", "1",
        "-c:a", "pcm_s16le", "-f", "s16le", str(dst),
    ], check=True, timeout=600)
    size = dst.stat().st_size
    if size == 0 or size % 2:
        raise ValueError(f"invalid decoded PCM: {src.name}")
    return size // 2


def encode_pcm(src: Path, dst: Path, sample_rate: int, bitrate: int, gain_db: float = 0.0) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "s16le",
        "-ar", str(sample_rate), "-ac", "1", "-i", str(src),
        "-af", f"volume={gain_db:.9f}dB", "-c:a", "libmp3lame",
        "-b:a", str(bitrate), str(dst),
    ], check=True, timeout=600)


# Anti-clip defaults (clone TTS true-peak >0 dBTP → audible clipping)
TRUE_PEAK_CEILING_DBTP = -1.0
SAMPLE_PEAK_CEILING_DBFS = -1.0


def measure_loudness(path: Path) -> dict:
    """EBU R128 measure via ffmpeg loudnorm print_format=json (true peak + integrated)."""
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
            "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=600,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if not m:
        raise RuntimeError(f"loudness_measure_failed: {proc.stderr[-800:]}")
    data = json.loads(m.group(0))
    return {k: data.get(k) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}


def measure_sample_peak_dbfs(path: Path) -> float:
    """Sample peak via volumedetect max_volume (dBFS)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    m = re.search(r"max_volume:\s*([-0-9.]+)\s*dB", proc.stderr)
    if not m:
        raise RuntimeError(f"volumedetect_failed: {proc.stderr[-500:]}")
    return float(m.group(1))


def apply_peak_limiter(src: Path, dst: Path, limit_db: float = -1.0, sample_rate: int = 32000, bitrate: int = 128000) -> None:
    """Peak-derived constant attenuation, with zero filter delay and no time stretch.

    The 1 dB encoding headroom bounds MP3 overshoot; the caller rechecks the result.
    Unlike lookahead/dynamic limiters this cannot move cue boundaries.
    """
    peak = max(measure_sample_peak_dbfs(src), float(measure_loudness(src)["input_tp"]))
    gain = min(0.0, limit_db - 1.0 - peak)
    subprocess.run([
        "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(src),
        "-af", f"volume={gain:.9f}dB", "-ar", str(sample_rate),
        "-ac", "1", "-c:a", "libmp3lame", "-b:a", str(bitrate), str(dst),
    ], check=True, timeout=600)


def ensure_no_clipping(mp3_path: Path, sample_rate: int = 32000, bitrate: int = 128000, *, source_pcm: Path | None = None) -> dict:
    """BLOCKING anti-clip gate after concat, before film mux.

    Measures sample peak + true peak. If either exceeds ceiling, apply zero-delay constant attenuation
    and re-measure. FAIL if still over ceiling (do not deliver hot audio).
    """
    sample_peak = measure_sample_peak_dbfs(mp3_path)
    loud = measure_loudness(mp3_path)
    tp = float(loud["input_tp"])
    report = {
        "sample_peak_dbfs": sample_peak,
        "true_peak_dbtp": tp,
        "integrated_lufs": float(loud["input_i"]) if loud.get("input_i") not in (None, "-inf") else None,
        "limiter_applied": False,
        "ceiling_dbtp": TRUE_PEAK_CEILING_DBTP,
        "ceiling_dbfs": SAMPLE_PEAK_CEILING_DBFS,
    }
    hot = sample_peak > SAMPLE_PEAK_CEILING_DBFS or tp > TRUE_PEAK_CEILING_DBTP
    if hot:
        limited = mp3_path.with_suffix(".limited.mp3")
        gain = min(SAMPLE_PEAK_CEILING_DBFS - sample_peak, TRUE_PEAK_CEILING_DBTP - tp) - 1.0
        if source_pcm is None:
            apply_peak_limiter(mp3_path, limited, limit_db=SAMPLE_PEAK_CEILING_DBFS, sample_rate=sample_rate, bitrate=bitrate)
        else:
            # Retry from the original PCM, never compound MP3 encoding losses/delay.
            encode_pcm(source_pcm, limited, sample_rate, bitrate, gain)
        report.update({"method": "constant_gain", "gain_db": gain, "latency_samples": 0})
        limited.replace(mp3_path)
        report["limiter_applied"] = True
        sample_peak = measure_sample_peak_dbfs(mp3_path)
        loud = measure_loudness(mp3_path)
        tp = float(loud["input_tp"])
        report.update({
            "sample_peak_dbfs": sample_peak,
            "true_peak_dbtp": tp,
            "integrated_lufs": float(loud["input_i"]) if loud.get("input_i") not in (None, "-inf") else None,
        })
    if sample_peak > SAMPLE_PEAK_CEILING_DBFS or tp > TRUE_PEAK_CEILING_DBTP:
        raise RuntimeError(
            f"anti_clip_FAIL sample_peak={sample_peak:.2f} dBFS true_peak={tp:.2f} dBTP "
            f"(ceilings {SAMPLE_PEAK_CEILING_DBFS}/{TRUE_PEAK_CEILING_DBTP}); do not mux"
        )
    return report


# ---------------- 本 skill 的入口：校验、缓存、逐条拼接、发布 ----------------
RATES = {8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000}
BITRATES = {8000, 16000, 24000, 32000, 40000, 48000, 56000, 64000, 80000, 96000, 112000, 128000, 144000, 160000, 192000, 224000, 256000, 320000}
HINTS = {
    "elevenlabs_api_key_missing": "缺 ElevenLabs 密钥：~/.config/elevenlabs/api-key 不存在（或设环境变量 ELEVENLABS_API_KEY）",
    "elevenlabs_private_directory_permissions_invalid": "~/.config/elevenlabs/ 须本人所有、组与其他人不可写（chmod 700）",
    "elevenlabs_private_key_permissions_invalid": "~/.config/elevenlabs/api-key 须本人所有、权限 600（chmod 600）",
    "elevenlabs_http_401": "密钥无效（HTTP 401）",
    "elevenlabs_http_402": "账户额度不足（HTTP 402）",
    "elevenlabs_http_403": "密钥没有文字转语音权限（HTTP 403）",
    "elevenlabs_http_404": "音色不存在或不属于这个账户（HTTP 404，核 voice-id）",
    "elevenlabs_http_429": "请求太频繁或并发超限（HTTP 429，重试三次仍不行）",
}


class SpecError(ValueError):
    pass


def _validate(spec):
    """在任何请求、缓存读写之前把整份 spec 核完；返回 (slug, cues, style, sample_rate, bitrate, gap_ms)。"""
    def ident(value, name):
        if not isinstance(value, str) or not re.fullmatch(r"\w[\w.-]{0,127}", value) or ".." in value or len(value.encode("utf-8")) > 180:
            raise SpecError(f"{name} 不合法：{value!r}")
    if not isinstance(spec, dict):
        raise SpecError("spec 须是 JSON 对象")
    if spec.get("provider") != "elevenlabs":
        raise SpecError(f"provider 必须是 \"elevenlabs\"（本 skill 只走 ElevenLabs），收到 {spec.get('provider')!r}")
    ident(spec.get("slug"), "slug")
    gap = spec.get("silence_gap_ms", 150)
    if isinstance(gap, bool) or not isinstance(gap, int) or not 0 <= gap <= 3600000:
        raise SpecError("silence_gap_ms 须是 0–3600000 的整数")
    rate, bitrate = spec.get("sample_rate", 32000), spec.get("bitrate", 128000)
    if isinstance(rate, bool) or rate not in RATES:
        raise SpecError(f"sample_rate 不合法：{rate!r}")
    if isinstance(bitrate, bool) or bitrate not in BITRATES:
        raise SpecError(f"bitrate 不合法：{bitrate!r}")
    style = spec.get("style")
    if style is not None and not isinstance(style, str):
        raise SpecError("style 须是字符串或 null")
    cues = spec.get("cues")
    if not isinstance(cues, list) or not cues:
        raise SpecError("cues 须是非空列表")
    seen = set()
    for cue in cues:
        if not isinstance(cue, dict):
            raise SpecError("每条 cue 须是对象")
        ident(cue.get("id"), "cue id")
        if cue["id"] in seen:
            raise SpecError(f"cue id 重复：{cue['id']}")
        seen.add(cue["id"])
        if not isinstance(cue.get("text"), str) or not cue["text"].strip():
            raise SpecError(f"cue {cue['id']} 的 text 为空")
        if not isinstance(cue.get("force_regenerate", False), bool):
            raise SpecError(f"cue {cue['id']} 的 force_regenerate 须是布尔值")
    return spec["slug"], cues, style or "", rate, bitrate, gap


def _cache_key(voice_id, tagged, rate, bitrate):
    key = {"schema": 1, "voice_fp": hashlib.sha256(voice_id.encode()).hexdigest()[:12], "model": MODEL, "styled_text": tagged,
           "voice_settings": VOICE_SETTINGS, "output_format": OUTPUT_FORMAT, "sample_rate": rate, "bitrate": bitrate}
    return hashlib.sha256(json.dumps(key, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), key


def _read_cache(cache, digest):
    mp3, rec = cache / f"{digest}.mp3", cache / f"{digest}.json"
    if not (mp3.is_file() and rec.is_file()):
        return None
    try:
        meta, data = json.loads(rec.read_text(encoding="utf-8")), mp3.read_bytes()
        if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
            return None
        return data, meta.get("generation") or {}
    except (ValueError, OSError, AttributeError):
        return None


def _write_cache(cache, digest, data, key, receipt):
    cache.mkdir(parents=True, exist_ok=True)
    gen = {k: v for k, v in receipt.items() if k != "voice_id"}   # 不落 voice ID 原文
    for name, payload in ((f"{digest}.mp3", data),
                          (f"{digest}.json", json.dumps({"sha256": hashlib.sha256(data).hexdigest(), "key": key, "generation": gen},
                                                        ensure_ascii=False, indent=1).encode("utf-8"))):
        with tempfile.NamedTemporaryFile(dir=cache, prefix=".tmp-", delete=False) as f:
            f.write(payload)
        os.replace(f.name, cache / name)


def _publish(out, slug, work):
    """两个文件逐个 os.replace（同一文件系统，各自原子）；第二个失败就把第一个还原成执行前的样子。"""
    names = [f"{slug}.mp3", f"{slug}.cues.json"]
    prev = {}
    for n in names:
        if (out / n).is_file():
            shutil.copy2(out / n, work / f"prev-{n}")
            prev[n] = work / f"prev-{n}"
    done = []
    try:
        for n in names:
            os.replace(work / n, out / n)
            done.append(n)
    except BaseException:
        for n in done:
            os.replace(prev[n], out / n) if n in prev else (out / n).unlink(missing_ok=True)
        raise


def generate(spec_path, out_dir):
    try:
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SpecError(f"spec 读不了：{e}") from None
    slug, cues, style, sample_rate, bitrate, base_gap_ms = _validate(spec)
    try:
        voice_id = resolve_voice()
    except ValueError:
        raise SpecError("环境变量 ELEVENLABS_TTS_VOICE_ID 没设或不是 20 位字母数字（make_audio.py 从 project.json 的 voice.elevenlabs.voice_id_file 读出后传入）") from None
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SpecError("PATH 里找不到 ffmpeg／ffprobe（project.json 的 ffmpeg_bin_dir 下要有）")
    plan = []   # 先把每条的读法稿、带风格标签的请求文本、缓存键都算好：任何一条不合法就在发请求前停
    for cue in cues:
        text = normalize_spoken_hyphens(html.unescape(cue["text"]))
        try:
            tagged = styled_text(text, style)
        except ValueError as e:
            raise SpecError(f"cue {cue['id']}：{e}") from None
        plan.append((cue, text, *_cache_key(voice_id, tagged, sample_rate, bitrate)))
    gap_ms_list = [effective_inter_cue_gap_ms(cue["text"], base_gap_ms) for cue in cues[:-1]]
    gap_samples = [(ms * sample_rate + 500) // 1000 for ms in gap_ms_list]
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    if os.environ.get("EF_ELEVENLABS_API_BASE"):
        print(f"注意：EF_ELEVENLABS_API_BASE 已设（只供测试），请求发往 {API_BASE}", file=sys.stderr, flush=True)
    # Do not unlink this lock: contenders must always lock the same inode.
    with (out / f".el-{slug}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f"同一输出目录里另一个 el_cued 正在合成 {slug}") from None
        need = [p for p in plan if p[0].get("force_regenerate") or _read_cache(cache, p[2]) is None]
        if need:
            resolve_key()   # 要发请求就先核密钥：缺密钥、权限不对在第一条请求前就停
        with tempfile.TemporaryDirectory(prefix=f".el-{slug}-attempt-", dir=out) as directory:
            work = Path(directory)
            timings, position, sent, hits = [], 0, 0, 0
            pcm = work / "combined.pcm"
            with pcm.open("wb") as combined:
                for i, (cue, text, digest, key) in enumerate(plan):
                    got = None if cue.get("force_regenerate") else _read_cache(cache, digest)
                    if got is not None:
                        data, gen = got
                        hit = True
                        hits += 1
                    else:
                        data, receipt = synthesize(text, style, voice_id, sample_rate, bitrate, 1, 120, ffmpeg, ffprobe)
                        _write_cache(cache, digest, data, key, receipt)
                        gen, hit = receipt, False
                        sent += 1
                    print(f"[{slug}] [{i + 1:02d}/{len(plan):02d}] {cue['id']}: {len(text)} chars{'（缓存）' if hit else ''}", flush=True)
                    fp = work / f"{i:04d}.audio"
                    fp.write_bytes(data)
                    piece = work / f"{i:04d}.pcm"
                    samples = decode_pcm(fp, piece, sample_rate)
                    with piece.open("rb") as source:
                        shutil.copyfileobj(source, combined)
                    timings.append({
                        "id": cue["id"], "start": position / sample_rate,
                        "end": (position + samples) / sample_rate,
                        "start_sample": position, "end_sample": position + samples,
                        "text": cue["text"],
                        "generation": {"provider": "elevenlabs", "model": gen.get("model") or MODEL,
                                       "request_id": gen.get("request_id"), "request_cache_hit": hit},
                    })
                    position += samples
                    if i < len(gap_samples):
                        # Bound memory even for unusually long requested pauses.
                        remaining = gap_samples[i] * 2
                        while remaining:
                            chunk = min(remaining, 1024 * 1024)
                            combined.write(bytes(chunk))
                            remaining -= chunk
                        position += gap_samples[i]
            final_mp3 = work / f"{slug}.mp3"
            encode_pcm(pcm, final_mp3, sample_rate, bitrate)
            anti_clip = ensure_no_clipping(final_mp3, sample_rate, bitrate, source_pcm=pcm)
            decoded_samples = decode_pcm(final_mp3, work / "verified.pcm", sample_rate)
            terminal_padding = 0
            if 0 < decoded_samples - position <= 47:
                # Some libmp3lame/decoder pairs emit at least 47 samples in a
                # very short final frame. Make that tail explicit in source PCM,
                # then require an exact decoded count; cue positions do not move.
                terminal_padding = decoded_samples - position
                with pcm.open("ab") as source:
                    source.write(bytes(2 * terminal_padding))
                position += terminal_padding
                encode_pcm(pcm, final_mp3, sample_rate, bitrate)
                anti_clip = ensure_no_clipping(final_mp3, sample_rate, bitrate, source_pcm=pcm)
                decoded_samples = decode_pcm(final_mp3, work / "verified.pcm", sample_rate)
            if decoded_samples != position:
                raise RuntimeError(f"encoded sample count mismatch: {decoded_samples} != {position}")
            anti_clip["latency_samples"] = 0
            anti_clip["decoded_sample_count_verified"] = True
            manifest = {
                "slug": slug, "duration": decoded_samples / sample_rate,
                "duration_computed": position / sample_rate,
                "container_duration": ffprobe_duration(final_mp3),
                "sample_rate": sample_rate, "channels": 1, "sample_format": "s16le",
                "total_samples": decoded_samples, "terminal_padding_samples": terminal_padding,
                "timing_basis": "decoded_pcm_samples",
                "audio_sha256": hashlib.sha256(final_mp3.read_bytes()).hexdigest(),
                "silence_gap_ms": base_gap_ms, "gap_ms_per_boundary": gap_ms_list,
                "gap_samples_per_boundary": gap_samples,
                "gap_s": gap_samples[0] / sample_rate if gap_samples else 0.0,
                "n_cues": len(cues), "requests_sent": sent, "cache_hits": hits,
                "anti_clip": anti_clip, "cues": timings,
            }
            (work / f"{slug}.cues.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _publish(out, slug, work)
    print(f"✓ {slug}.mp3  {manifest['duration']:.3f}s; {len(cues)} cues（请求 {sent} 条、缓存 {hits} 条）; sample drift=0")
    return manifest


def main():
    if len(sys.argv) != 3:
        print("用法：el_cued.py <spec.json> <out_dir>", file=sys.stderr)
        return 2
    try:
        generate(sys.argv[1], sys.argv[2])
    except SpecError as e:
        print(f"el_cued: {e}", file=sys.stderr)
        return 2
    except (ElevenLabsUnavailableError, ElevenLabsHardError) as e:
        print(f"el_cued: ElevenLabs 不可用：{e}" + (f"——{HINTS[str(e)]}" if str(e) in HINTS else ""), file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"el_cued: 失败：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
