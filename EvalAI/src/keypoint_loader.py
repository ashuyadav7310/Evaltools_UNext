# src/keypoint_loader.py

"""
Loads keypoints for content rubrics
"""

import os
import re
from typing import Dict, List

from docx import Document
from src.logging_config import get_logger

log = get_logger("keypoints")


def _keypoints_dir(assignment_id: str) -> str:
    return os.path.join("input_data", "Assignments", assignment_id, "keypoints")


def _load_keypoints_from_docx(path: str) -> List[str]:
    doc = Document(path)
    kps: List[str] = []

    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue

        # More robust bullet/number stripping
        text = re.sub(r"^[\-\•\●\▪\■\□\▶\➤\d\)\.\s]+", "", text).strip()
        if text:
            kps.append(text)

    return kps


def load_keypoints_if_any(
    assignment_id: str,
    rubrics: List[Dict],
) -> Dict[str, List[str]]:
    """
    Loads keypoints only when the rubric defines:
      requires_keypoints = true  AND  keypoints_file is provided.

    Returns:
      {rubric_id: [kp1, kp2, ...]}
    """
    base = _keypoints_dir(assignment_id)
    out: Dict[str, List[str]] = {}

    if not os.path.isdir(base):
        return out

    for r in rubrics:
        rid = r.get("id") or r.get("rubric_id") or ""
        if not rid:
            continue

        if not r.get("requires_keypoints"):
            continue

        kp_file = r.get("keypoints_file")
        if not kp_file:
            continue

        path = os.path.join(base, kp_file)
        if not os.path.isfile(path):
            log.warning("Keypoints file missing for %s → %s", rid, path)
            continue

        try:
            kps = _load_keypoints_from_docx(path)
            if kps:
                out[rid] = kps
                log.info("Keypoint mode ACTIVATED for %s (%d keypoints)", rid, len(kps))
            else:
                log.warning("Keypoints file %s for %s is empty.", path, rid)
        except Exception as e:
            log.error("Failed to load keypoints for %s from %s: %s", rid, path, e)

    return out
