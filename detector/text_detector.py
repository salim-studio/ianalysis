"""Heuristic AI-text detector (Arabic + English).

Combines: lexical diversity (TTR), burstiness (sentence-length variance),
repetition, connective overuse, punctuation uniformity — typical LLM traces.
Returns score 0..1 + verdict: watermarked / uncertain / not_watermarked.
"""
import re
from collections import Counter

AI_PHRASES_AR = ["في الختام", "تجدر الإشارة", "علاوة على ذلك", "بشكل عام",
                 "من المهم أن", "في عالم", "يلعب دورا", "تسليط الضوء", "بمثابة"]
AI_PHRASES_EN = ["in conclusion", "moreover", "furthermore", "additionally",
                 "it is important to note", "as an ai", "delve", "tapestry",
                 "in today's fast-paced world", "overall,"]

def _sentences(text):
    parts = re.split(r"[.!?؟\n]+", text)
    return [p.strip() for p in parts if p.strip()]

def analyze_text(text: str):
    text = (text or "").strip()
    words = re.findall(r"[\w\u0600-\u06FF]+", text, flags=re.UNICODE)
    n = len(words)
    if n < 10:
        return {"score": 0.0, "verdict": "uncertain",
                "details": {"reason": "نص قصير جدًا — لا يمكن الحكم (أدخل 50+ كلمة لدقة أفضل)"},
                "signals": {}}
    uniq = len(set(w.lower() for w in words))
    ttr = uniq / max(n, 1)  # low TTR → repetitive → more AI-like
    sents = _sentences(text)
    lens = [len(s.split()) for s in sents if s.split()]
    if len(lens) >= 3:
        mean = sum(lens) / len(lens)
        var = sum((l - mean) ** 2 for l in lens) / len(lens)
        burst = var / (mean + 1e-6)  # high burst → human-like
    else:
        burst, mean, var = 0, 0, 0

    low = text.lower()
    phrase_hits = sum(1 for p in AI_PHRASES_AR + AI_PHRASES_EN if p in low)

    # repetition of 3-grams
    grams = [" ".join(words[i:i+3]).lower() for i in range(max(len(words)-2, 0))]
    rep = 0
    if grams:
        c = Counter(grams)
        rep = sum(v - 1 for v in c.values() if v > 1) / max(len(grams), 1)

    # Punctuation uniformity: humans vary (! ؟ ...), LLMs mostly . ، ,
    punct = re.findall(r"[.,!?:;،؛؟…\-—\"'()]", text)
    punct_score = 0.0
    if punct:
        pc = Counter(punct)
        top = pc.most_common(1)[0][1] / len(punct)
        punct_score = max(0.0, (top - 0.4) / 0.6)  # dominated by one mark → AI-like

    # Scoring: each signal 0..1 (higher = more AI-like)
    s_ttr = max(0.0, min(1.0, (0.75 - ttr) / 0.45)) if n > 30 else max(0.0, min(1.0, (0.85 - ttr) / 0.5))
    s_burst = max(0.0, min(1.0, 1.0 - burst / 8.0))
    s_rep = max(0.0, min(1.0, rep / 0.08))
    s_phrase = min(1.0, phrase_hits / 3.0)

    score = 0.30 * s_ttr + 0.25 * s_burst + 0.20 * s_rep + 0.15 * s_phrase + 0.10 * punct_score
    score = float(max(0.01, min(0.99, score)))

    if score >= 0.7:
        verdict = "watermarked"
    elif score >= 0.4:
        verdict = "uncertain"
    else:
        verdict = "not_watermarked"

    return {
        "score": round(score, 3),
        "verdict": verdict,
        "details": {
            "words": n, "sentences": len(lens),
            "lexical_diversity": round(ttr, 3),
            "burstiness": round(float(burst), 2),
            "phrase_hits": phrase_hits,
        },
        "signals": {
            "lexical": round(float(s_ttr), 3),
            "burst": round(float(s_burst), 3),
            "repetition": round(float(s_rep), 3),
            "phrases": round(float(s_phrase), 3),
            "punctuation": round(float(punct_score), 3),
        },
    }
