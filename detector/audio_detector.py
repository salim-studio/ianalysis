"""Audio/Video heuristic detector.

- Scans container metadata bytes for AI TTS/VC keywords (elevenlabs, suno, udio,
  murf, tts, bark, xtts, sovits, diffsinger, veo, pika, runway, synthid...).
- For WAV: spectral flatness + zero-crossing analysis (neural vocoders are
  over-smooth vs. noisy mic recordings).
- For video (mp4/webm): metadata scan + note that frame-level scan needs ffmpeg.
"""
import io
import wave
import numpy as np

AI_AUDIO_KW = ["elevenlabs", "suno", "udio", "murf", "play.ht", "playht",
               "tts", "text-to-speech", "bark", "xtts", "sovits", "diffsinger",
               "rvc", "so-vits", "veo", "pika", "runway", "synthid", "lovo",
               "resemble", "descript", "lyria", "musiclm", "audiolm"]

def _kw_scan(raw: bytes):
    low = raw[:3_000_000].decode("utf-8", errors="ignore").lower()
    return [k for k in AI_AUDIO_KW if k in low]

def _wav_stats(raw: bytes):
    try:
        with wave.open(io.BytesIO(raw), "rb") as w:
            n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
            frames = w.readframes(min(n, sr * 20))  # first 20s
            sampwidth = w.getsampwidth()
    except Exception:
        return None
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sampwidth, np.int16)
    try:
        y = np.frombuffer(frames, dtype=dtype).astype(np.float32)
    except Exception:
        return None
    if y.size == 0:
        return None
    if ch > 1:
        y = y.reshape(-1, ch).mean(axis=1)
    y /= (np.abs(y).max() + 1e-9)
    # zero-crossing rate
    zcr = float(((y[:-1] * y[1:]) < 0).mean())
    # spectral flatness over windows
    N = 2048
    flats = []
    for i in range(0, max(len(y) - N, 1), N * 2):
        seg = y[i:i+N] * np.hanning(min(N, len(y[i:i+N])))
        S = np.abs(np.fft.rfft(seg)) + 1e-9
        flats.append(float(np.exp(np.log(S).mean()) / S.mean()))
    flat = float(np.mean(flats)) if flats else 0.5
    # Neural vocoder audio: very smooth spectrum (high flatness) + steady ZCR
    s_flat = max(0.0, min(1.0, (flat - 0.15) / 0.5))
    s_zcr = max(0.0, min(1.0, 1.0 - abs(zcr - 0.06) / 0.10))
    stat = 0.6 * s_flat + 0.4 * s_zcr
    return {"flatness": round(flat, 3), "zcr": round(zcr, 4),
            "stat_score": round(float(stat), 3), "sr": sr, "channels": ch}

def analyze_audio(raw: bytes, filename: str = ""):
    hits = _kw_scan(raw)
    if hits:
        return {"score": 0.95, "verdict": "watermarked",
                "details": {"metadata_hits": hits, "file": filename}}
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext in ("wav", "wave") or raw[:4] == b"RIFF":
        st = _wav_stats(raw)
        if st:
            s = st.pop("stat_score")
            v = "watermarked" if s >= 0.7 else ("uncertain" if s >= 0.4 else "not_watermarked")
            return {"score": round(s, 3), "verdict": v, "details": st}
    # generic compressed audio: can't do deep forensics without decode libs
    return {"score": 0.5, "verdict": "uncertain",
            "details": {"note": "لا توجد علامات provenance في البيانات الوصفية. الملف مضغوط (mp3/ogg/m4a) — التحليل الطيفي الدقيق يتطلب فك التشفير. النتيجة محايدة.",
                        "metadata_hits": hits, "file": filename}}

def analyze_video(raw: bytes, filename: str = ""):
    low = raw[:3_000_000].decode("utf-8", errors="ignore").lower()
    vkw = AI_AUDIO_KW + ["veo", "sora", "pika", "runway", "gen-3", "luma",
                         "stable video", "deforum", "animatediff"]
    hits = [k for k in vkw if k in low]
    if hits:
        return {"score": 0.95, "verdict": "watermarked",
                "details": {"metadata_hits": hits, "file": filename,
                            "size_mb": round(len(raw) / 1e6, 2)}}
    return {"score": 0.5, "verdict": "uncertain",
            "details": {"note": "لا توجد علامات provenance في حاوية الفيديو. كشف إطارات الفيديو المولّد يحتاج FFmpeg/OpenCV — النتيجة محايدة.",
                        "file": filename, "size_mb": round(len(raw) / 1e6, 2)}}
