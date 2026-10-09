"""Image AI-generation detector (ianalysis engine).

Combines:
 1) Metadata / provenance scan (EXIF, PNG info, XMP, C2PA/Content Credentials markers)
 2) Frequency-domain analysis (FFT high-frequency energy — diffusion models leave traces)
 3) Noise / texture statistics
into a probabilistic score 0..1.
"""
from PIL import Image, ExifTags
import numpy as np
import io

AI_KEYWORDS = [
    "ai generated", "generated with ai", "artificial intelligence",
    "midjourney", "dall-e", "dalle", "stable diffusion", "sdxl",
    "firefly", "adobe firefly", "imagen", "gemini",
    "c2pa", "content credentials", "openai", "leonardo", "bing image",
    "ideogram", "flux", "comfyui", "automatic1111", "invokeai",
]

def _metadata_scan(img: Image.Image, raw_bytes: bytes):
    hits = []
    score = 0.0
    # 1. PIL info dict (PNG text chunks etc.)
    try:
        info = dict(getattr(img, "info", {}) or {})
        blob = " ".join([f"{k}={v}" for k, v in info.items()]).lower()
        for kw in AI_KEYWORDS:
            if kw in blob:
                hits.append(f"PNG/Text chunk: {kw}")
                score = max(score, 0.95)
    except Exception:
        pass
    # 2. EXIF
    try:
        exif = img.getexif()
        if exif:
            txt = ""
            for tag_id, val in exif.items():
                try:
                    txt += f" {ExifTags.TAGS.get(tag_id, tag_id)}={val}"
                except Exception:
                    txt += f" {val}"
            low = txt.lower()
            for kw in AI_KEYWORDS:
                if kw in low:
                    hits.append(f"EXIF: {kw}")
                    score = max(score, 0.95)
            if "software" in low or "model" in low:
                hits.append("EXIF software tag present")
                score = max(score, min(score + 0.1, 0.5))
    except Exception:
        pass
    # 3. Raw byte search (XMP / C2PA / JUMBF markers survive in file)
    try:
        low = raw_bytes[:2_000_000].decode("utf-8", errors="ignore").lower()
        for kw in AI_KEYWORDS:
            if kw in low and not any(kw in h.lower() for h in hits):
                hits.append(f"Embedded marker: {kw}")
                score = max(score, 0.95)
        if "jumb" in low or "c2pa" in low:
            hits.append("C2PA/JUMBF provenance block found")
            score = max(score, 0.7)
    except Exception:
        pass
    return score, hits


def _frequency_analysis(gray: np.ndarray):
    """Diffusion/GAN images often show abnormal FFT spectrum smoothness / grid artifacts."""
    h, w = gray.shape
    # downsample for speed
    small = gray
    if max(h, w) > 512:
        import PIL.Image as PImg
        im = PImg.fromarray(gray).resize((512, int(h * 512 / w)))
        small = np.asarray(im, dtype=np.float32)
    f = np.fft.fftshift(np.fft.fft2(small - small.mean()))
    mag = np.abs(f)
    cy, cx = mag.shape[0] // 2, mag.shape[1] // 2
    yy, xx = np.ogrid[:mag.shape[0], :mag.shape[1]]
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    maxr = dist.max()
    low = mag[dist < maxr * 0.15].mean()
    mid = mag[(dist >= maxr * 0.15) & (dist < maxr * 0.5)].mean()
    high = mag[dist >= maxr * 0.5].mean()
    high_ratio = float(high / (low + 1e-6))
    mid_ratio = float(mid / (low + 1e-6))
    # Natural photos: high_ratio typically 0.05–0.25. Over-smooth AI: very low or oddly flat.
    # Score peaks when spectrum is abnormally smooth (low high-freq) + mid boosted (diffusion hump).
    smoothness = 1.0 - min(high_ratio / 0.25, 1.0)  # 1 = very smooth
    hump = 1.0 - abs(mid_ratio - 0.45) / 0.45
    hump = max(0.0, min(1.0, hump))
    fft_score = 0.55 * smoothness + 0.45 * hump
    return float(np.clip(fft_score, 0, 1)), {
        "high_ratio": round(high_ratio, 4),
        "mid_ratio": round(mid_ratio, 4),
    }


def _noise_analysis(gray: np.ndarray):
    """Sensor noise (PRNU) is irregular; AI images have uniform denoised texture."""
    lap = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    from scipy_signals import convolve_fallback
    resp = convolve_fallback(gray, lap)
    var = float(resp.var())
    # Natural photo Laplacian variance usually large (>200); clean AI render often <80
    if var < 40:
        s = 0.9
    elif var < 80:
        s = 0.75
    elif var < 150:
        s = 0.55
    elif var < 300:
        s = 0.35
    else:
        s = 0.15
    return s, {"laplacian_var": round(var, 2)}


def analyze_image(file_bytes: bytes):
    img = Image.open(io.BytesIO(file_bytes))
    img.load()
    meta_score, hits = _metadata_scan(img, file_bytes)

    rgb = img.convert("RGB")
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)

    fft_score, fft_info = _frequency_analysis(gray)

    # Laplacian without scipy dependency
    padded = np.pad(gray, 1)
    lap_resp = (padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:] - 4 * gray)
    var = float(lap_resp.var())
    if var < 40:
        noise_score = 0.9
    elif var < 80:
        noise_score = 0.75
    elif var < 150:
        noise_score = 0.55
    elif var < 300:
        noise_score = 0.35
    else:
        noise_score = 0.15

    # Color histogram smoothness: AI gradients are overly smooth
    hist_var = float(np.asarray(rgb).std())
    if hist_var < 35:
        color_score = 0.7
    elif hist_var < 55:
        color_score = 0.5
    else:
        color_score = 0.3

    stat_score = 0.45 * fft_score + 0.35 * noise_score + 0.20 * color_score

    # If provenance metadata says AI → trust it strongly
    if meta_score >= 0.9:
        final = 0.97
        verdict = "ai_generated"
    else:
        final = float(np.clip(stat_score, 0.01, 0.99))
        if final >= 0.7:
            verdict = "ai_generated"
        elif final >= 0.4:
            verdict = "uncertain"
        else:
            verdict = "human"

    details = {
        "metadata_hits": hits,
        "fft": fft_info,
        "laplacian_var": round(var, 2),
        "color_std": round(hist_var, 2),
        "stat_score": round(stat_score, 3),
        "size": f"{img.width}x{img.height}",
        "format": img.format,
    }
    return {"score": round(final, 3), "verdict": verdict, "details": details}
