"""ianalysis (Flask). Detects AI-generation likelihood for image/audio/video/text."""
from flask import Flask, request, jsonify, render_template
from detector.image_detector import analyze_image
from detector.text_detector import analyze_text
from detector.audio_detector import analyze_audio, analyze_video

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

ALLOWED_IMG = {"png", "jpg", "jpeg", "webp", "bmp"}
ALLOWED_AUD = {"mp3", "wav", "ogg", "m4a", "flac", "aac"}
ALLOWED_VID = {"mp4", "webm", "mov", "mkv"}

def ext_of(name):
    return (name.rsplit(".", 1)[-1] if "." in (name or "") else "").lower()

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/detect-image")
def detect_image():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Please upload an image first"}), 400
    raw = f.read()
    if len(raw) > 50 * 1024 * 1024:
        return jsonify({"error": "File too large (>50MB)"}), 400
    try:
        res = analyze_image(raw)
    except Exception as e:
        return jsonify({"error": f"Could not read image: {e}"}), 400
    return jsonify(res)

@app.post("/api/detect-audio")
def detect_audio():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Please upload an audio/video file first"}), 400
    raw = f.read()
    ext = ext_of(f.filename)
    if ext in ALLOWED_VID:
        return jsonify(analyze_video(raw, f.filename))
    return jsonify(analyze_audio(raw, f.filename))

@app.post("/api/detect-text")
def detect_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "") or request.form.get("text", "")
    if not text.strip():
        return jsonify({"error": "Please enter some text first"}), 400
    return jsonify(analyze_text(text))

@app.get("/api/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
