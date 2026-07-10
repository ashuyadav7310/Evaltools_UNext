# src/format_evidence.py

from typing import Dict, Any
from src.logging_config import get_logger

log = get_logger("format_evidence")

def score_table_depth(table_meta: dict) -> float:
    """
    Deterministic table-structure depth scoring.
    FORMAT evidence only.
    """
    score = 0.0

    rows = table_meta.get("rows") or 0
    cols = table_meta.get("cols") or 0
    has_header = table_meta.get("has_header", False)

    try:
        rows = int(rows)
    except (TypeError, ValueError):
        rows = 0

    try:
        cols = int(cols)
    except (TypeError, ValueError):
        cols = 0

    if rows >= 1:
        score += 0.3
    if rows >= 3:
        score += 0.25
    if cols >= 3:
        score += 0.25
    if has_header:
        score += 0.2

    return min(score, 1.0)

def extract_format_evidence(doc_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract STRUCTURAL and VISUAL evidence for format scoring.
    This function NEVER assigns marks.
    It only reports what is present.
    """

    # Tables & diagrams now come as structured lists from loader
    tables = doc_meta.get("tables", [])
    images_detected = doc_meta.get("images_detected", 0)

    tables_detected = len(tables)

    # Table depth heuristic (structural richness, NOT scoring)
    max_table_depth = 0.0
    for t in tables:
        try:
            max_table_depth = max(max_table_depth, score_table_depth(t))
        except Exception:
            continue


    evidence = {
        # Text structure
        "images_detected": doc_meta.get("images_detected", 0),
        "paragraph_blocks": doc_meta.get("paragraph_blocks", 0),

        # Lists
        "bullet_lists": doc_meta.get("bullet_lists", 0),
        "numbered_lists": doc_meta.get("numbered_lists", 0),

        # Tables
        "tables_detected": tables_detected,
        "max_table_depth": max_table_depth,
    }

    log.debug("Format evidence extracted → %s", evidence)
    return evidence