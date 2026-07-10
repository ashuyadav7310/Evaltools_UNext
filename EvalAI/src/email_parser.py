# src/email_parser.py
import re
from typing import Any, Dict

GREETING_PATTERNS = [
    r"^dear\b",
    r"^hi\b",
    r"^hello\b",
    r"^respected\b",
    r"^good (morning|afternoon|evening)\b",
    r"^to whom it may concern\b",
]

CLOSING_PATTERNS = [
    r"^regards\b",
    r"^best regards\b",
    r"^kind regards\b",
    r"^warm regards\b",
    r"^thanks( and regards)?\b",
    r"^sincerely\b",
    r"^thank you\b",
    r"^yours faithfully\b",
    r"^yours sincerely\b",
    r"^best\b",
]


def _clean_line_for_match(line: str) -> str:
    return re.sub(r"[,\.\!\s]+$", "", line.strip().lower())


def _looks_like_name(line: str) -> bool:
    token_count = len(line.split())
    if token_count < 1 or token_count > 5:
        return False
    if re.search(r"\d", line):
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z\.\'\-]*(?:\s+[A-Za-z][A-Za-z\.\'\-]*){0,4}$", line))


def extract_email_features(full_text: str) -> Dict[str, Any]:
    """
    Lightweight rule-based email structure detection.
    """

    if not full_text:
        return {}

    lines = [l.strip() for l in full_text.splitlines() if l.strip()]

    # Subject detection
    subject_present = any(re.match(r"^subject\s*[:\-]", l.lower()) for l in lines)

    # Greeting detection (check first 3 lines)
    greeting_idx = -1
    for i in range(min(3, len(lines))):
        cleaned = _clean_line_for_match(lines[i])
        if any(re.match(p, cleaned) for p in GREETING_PATTERNS):
            greeting_idx = i
            break
    greeting_present = greeting_idx >= 0

    # Closing detection (check last 5 lines)
    closing_idx = -1
    for i in range(max(0, len(lines) - 5), len(lines)):
        cleaned = _clean_line_for_match(lines[i])
        if any(re.match(p, cleaned) for p in CLOSING_PATTERNS):
            closing_idx = i
            break
    closing_present = closing_idx >= 0

    # Signature detection (common email sign-off patterns)
    signature_present = False
    if closing_present and len(lines) >= 2 and closing_idx < len(lines) - 1:
        tail_lines = lines[closing_idx + 1: closing_idx + 4]
        for line in tail_lines:
            if _looks_like_name(line):
                signature_present = True
                break
            if "@" in line or re.search(r"\+?\d[\d\-\s]{6,}\d", line):
                signature_present = True
                break
    elif len(lines) >= 1:
        last_line = lines[-1]
        if _looks_like_name(last_line):
            signature_present = True

    # Paragraph count
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", full_text) if p.strip()]
    if not paragraphs and full_text.strip():
        paragraphs = [full_text.strip()]
    paragraph_count = len(paragraphs)

    # ALL CAPS ratio
    letters = [c for c in full_text if c.isalpha()]
    caps_ratio = (
        sum(c.isupper() for c in letters) / len(letters)
        if letters else 0.0
    )

    # Excess punctuation
    excessive_punct = len(re.findall(r"[!]{2,}|[?]{2,}", full_text))

    # Basic body adequacy features (excluding common structural lines)
    body_lines = lines[:]
    body_lines = [l for l in body_lines if not re.match(r"^subject\s*[:\-]", l.lower())]
    if greeting_idx >= 0 and greeting_idx < len(body_lines):
        body_lines = [l for idx, l in enumerate(body_lines) if idx != greeting_idx]
    if closing_idx >= 0:
        body_lines = body_lines[:max(0, closing_idx)]
    body_text = " ".join(body_lines).strip()
    body_word_count = len(re.findall(r"\b\w+\b", body_text))
    body_sentence_count = len([s for s in re.split(r"[.!?]+", body_text) if s.strip()])

    return {
        "subject_present": subject_present,
        "greeting_present": greeting_present,
        "closing_present": closing_present,
        "signature_present": signature_present,
        "paragraph_count": paragraph_count,
        "caps_ratio": caps_ratio,
        "excess_punctuation": excessive_punct,
        "body_word_count": body_word_count,
        "body_sentence_count": body_sentence_count,
    }
