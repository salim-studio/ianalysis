# ianalysis — نسخة عربية (شبيه synthid.com)

بوابة فحص المحتوى المولّد بالذكاء الاصطناعي: صور / صوت / فيديو / نص.
واجهة عربية RTL + باك إند Flask.

> ⚠️ أداة تعليمية تحاكي فكرة SynthID Detector. ليست مفتاح Google الرسمي —
> النتائج احتمالية (0–100%) وليست دليلًا قاطعًا.

## التشغيل

```bash
cd ianalysis
pip install -r requirements.txt
python app.py
```

ثم افتح: http://127.0.0.1:5000

## الواجهات (API)

| المسار | الطريقة | الدخل | الخرج |
|---|---|---|---|
| `/api/detect-image` | POST | `file` (png/jpg/webp/bmp) | `{score, verdict, details}` |
| `/api/detect-audio` | POST | `file` (mp3/wav/m4a/mp4/webm) | `{score, verdict, details}` |
| `/api/detect-text` | POST | JSON `{"text": "..."}` | `{score, verdict, details, signals}` |

`verdict`: `watermarked` (غالبًا AI) / `uncertain` / `not_watermarked` (غالبًا بشري)

## كيف يعمل الكشف؟

- **الصور** (`detector/image_detector.py`): فحص EXIF/XMP/C2PA للكلمات المفتاحية (Midjourney, DALL-E, SynthID...) + تحليل FFT للترددات + تجانس الضجيج (Laplacian).
- **الصوت** (`detector/audio_detector.py`): فحص علامات TTS (elevenlabs, suno...) + تحليل طيفي لملفات WAV.
- **الفيديو**: فحص حاوية الملف لعلامات (veo, sora, pika...).
- **النص** (`detector/text_detector.py`): التنوع المعجمي، الانفجارية، التكرار، العبارات النمطية — عربي + إنجليزي.

## ملاحظات

- الجودة العالية بدون ضغط تعطي أفضل النتائج (مثل الأصل).
- التعديلات الشديدة تُضعف الإشارة.
