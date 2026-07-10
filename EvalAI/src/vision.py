# src/vision.py
"""
Vision understanding using OpenAI multimodal models.
Pure extraction only. NO scoring. NO evaluation.
"""

import base64
import os
import json
import re
from typing import Dict, Any
import hashlib
from openai import OpenAI
from dotenv import load_dotenv
from src.logging_config import get_logger

load_dotenv()
# Vision cache (per-process, safe, memory-only)

_VISION_CACHE: Dict[str, Dict[str, Any]] = {}

log = get_logger("vision")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VISION_MODEL = "gpt-4.1-mini"  # Correct + cost-efficient

def _safe_parse_json(raw: str) -> Dict[str, Any]:
    raw = raw.strip()

    # Remove markdown fences
    raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Extract first JSON object safely
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}

    return json.loads(match.group())

def _detect_mime(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        return "image/webp"
    return "image/png"

def analyze_image_semantics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Analyze an image and return structured semantic understanding.
    """
    # ------------------------------------------------------------
    # CACHE KEY (hash image bytes)
    # ------------------------------------------------------------
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    cached = _VISION_CACHE.get(img_hash)
    if cached:
        log.debug("[VISION] Cache hit → skipping OpenAI call")
        return cached
    
    if image_bytes.startswith(b"<svg"):
        log.warning("[VISION] SVG image detected – skipping OpenAI call")
        return {
            "image_type": "vector_diagram",
            "brief_summary": "Vector diagram detected (SVG).",
            "key_entities": [],
            "relevance_score": 0.0,
            "correctness_score": 0.0,
            "completeness_score": 0.0
        }

    log.debug("[VISION] analyze_image_semantics called | bytes=%d", len(image_bytes))
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = _detect_mime(image_bytes)

    prompt = """
You are analyzing an image from a student assignment.

TASK:
Visually analyze the image ONLY. Do not use external knowledge.

Return the following STRICT JSON fields:

- image_type: one of [table, architecture_diagram, flowchart, chart, other]
- brief_summary: 2–3 lines describing what the image conveys
- key_entities: list of visible components or concepts

IMAGE QUALITY CHECKS:
- relevance_score: float (0.0–1.0) — how relevant this image is to a system architecture / case-study style answer
- correctness_score: float (0.0–1.0) — whether the image appears technically/logically correct
- completeness_score: float (0.0–1.0) — whether the image appears complete and self-contained

RULES:
- Base judgments ONLY on what is visible
- Do not assume missing labels
- Do not hallucinate
- Return STRICT JSON only
"""

    response = client.responses.create(
        model=VISION_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
               {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{image_b64}"
                }
            ]
        }],
        max_output_tokens=400
    )

    raw_text = response.output_text or ""

    try:
        result = _safe_parse_json(raw_text) or {}

        normalized = {
            "image_type": result.get("image_type", "other"),
            "brief_summary": result.get("brief_summary", ""),
            "key_entities": result.get("key_entities", []),
            "relevance_score": float(result.get("relevance_score", 0.0)),
            "correctness_score": float(result.get("correctness_score", 0.0)),
            "completeness_score": float(result.get("completeness_score", 0.0)),
        }

        log.debug(
            "[VISION] Semantic summary generated (len=%d): %s",
            len(normalized["brief_summary"]),
        )
        _VISION_CACHE[img_hash] = normalized
        return normalized

    except Exception:
        log.exception(
            "[VISION] JSON parse failed. Raw output (truncated): %s",
            raw_text[:500]
        )

        fallback =  {
            "image_type": "other",
            "brief_summary": raw_text.strip()[:300],
            "key_entities": [],
            "relevance_score": 0.0,
            "correctness_score": 0.0,
            "completeness_score": 0.0
        }
        _VISION_CACHE[img_hash] = fallback
        return fallback
