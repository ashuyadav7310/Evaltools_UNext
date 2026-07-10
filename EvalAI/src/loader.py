# src/loader.py
"""
RESPONSIBILITY:
- Extract raw text
- Detect tables, diagrams, images
- Run vision model on images
- Attach structural evidence (NO scoring)
"""

from __future__ import annotations
import os
from typing import Dict, Any, List, Tuple
import fitz  # PyMuPDF
import docx
import pdfplumber
import hashlib
import re
from statistics import median
from src.logging_config import get_logger
from src.vision import analyze_image_semantics

log = get_logger("loader")
SEEN_IMAGE_HASHES = set()

# Table metadata extraction (rows, cols, header presence)
def extract_table_meta(rows: List[List[str]]) -> Dict[str, Any]:
    return {
        "rows": len(rows),
        "cols": len(rows[0]) if rows else 0,
        "has_header": any(len(c) > 2 and c.replace(" ", "").isalpha()
         for c in rows[0]) if rows else False
        }

# Atomic splitting of dense table rows (for better embedding performance)
def _atomic_split_table_row(row_text: str) -> List[str]:
    """
    Split dense table rows into meaningful semantic fragments
    without breaking technical phrases.Why? Because 
    Embedding models struggle with dense table rows.
    """
    if not row_text:
        return []

    # Split only on strong structural separators
    parts = re.split(r"\||;|→", row_text)

    cleaned = []
    for p in parts:
        p = p.strip()
        if len(p.split()) >= 3:
            cleaned.append(p)

    return cleaned

# DOCX — Inline extraction (text + tables + images)
log.info("Starting DOCX inline extraction")

def _extract_docx_text_inline(
    doc: docx.Document
) -> Tuple[str, bool, Dict[str, Any]]:

    paragraphs: List[str] = []
    has_images = False

    doc_meta = {
        "tables": [],
        "table_texts": [],
        "images": [],
        "images_detected": 0,  
        "paragraph_blocks": 0,
        "bullet_lists": 0,
        "numbered_lists": 0
    }

    # ---- Vision re-entry guard ----
    if doc_meta.get("vision_done"):
        log.info("Skipping vision: already processed for this document")
        return "\n".join(paragraphs), has_images, doc_meta

    for element in doc.element.body:
        tag = element.tag.lower()

        # PARAGRAPHS (TEXT + INLINE IMAGES)
        if tag.endswith("}p"):
            para = docx.text.paragraph.Paragraph(element, doc)

            # INLINE IMAGE DETECTION (CRITICAL)
            for run in para.runs:
                if "graphicData" in run._element.xml:
                    has_images = True
                    paragraphs.append("[[IMAGE_PLACEHOLDER]]")
                    doc_meta["images_detected"] += 1

            text = (para.text or "").strip()
            if text:
                paragraphs.append(text)

                if len(text.split()) > 6:
                    doc_meta["paragraph_blocks"] += 1
                if text.startswith(("-", "•", "*")):
                    doc_meta["bullet_lists"] += 1
                if text[:2].isdigit():
                    doc_meta["numbered_lists"] += 1

        # TABLES 
        elif tag.endswith("}tbl"):
            tbl = docx.table.Table(element, doc)

            rows = [
                [(cell.text or "").strip() for cell in row.cells]
                for row in tbl.rows
            ]

            table_meta = extract_table_meta(rows)
            
            flat_rows = []

            for row in rows:
                for cell in row:
                    cell_text = (cell or "").strip()

                    if not cell_text:
                        continue

                    # Split inside cell if needed (but do NOT flatten row)
                    atomic_parts = _atomic_split_table_row(cell_text)

                    if atomic_parts:
                        flat_rows.extend(atomic_parts)
                    else:
                        if len(cell_text.split()) >= 3:
                            flat_rows.append(cell_text)

            flat_table_text = "\n".join(flat_rows)

            doc_meta["table_texts"].append(flat_table_text)

            paragraphs.append(
                "[TABLE CONTENT START]\n"
                + flat_table_text +
                "\n[TABLE CONTENT END]"
            )
            doc_meta["tables"].append(table_meta)

    # ---------- COLLECT IMAGES ----------
    images: List[bytes] = []

    for rel in doc.part._rels.values():
        if "image" not in str(rel.reltype).lower():
            continue

        # Skip externally linked images (no embedded blob)
        try:
            if rel.is_external:
                log.debug("Skipping external image link")
                continue

            images.append(rel.target_part.blob)

        except Exception:
            log.debug("Failed to extract embedded image blob")
            continue


    # ---------- SECOND PASS: IMAGE PROCESSING ----------
    img_idx = 0
    for i, val in enumerate(paragraphs):
        if val != "[[IMAGE_PLACEHOLDER]]" or img_idx >= len(images):
            continue

        blob = images[img_idx]
        img_idx += 1  # increment ONCE

        # IMAGE FORMAT GUARD
        if blob.startswith(b"<svg") or b"svg" in blob[:200].lower():
            log.debug("SVG image detected → skipping vision model")
            paragraphs[i] = "[IMAGE PRESENT – VECTOR GRAPHIC NOT ANALYZED]"
            doc_meta["images"].append({
                "summary": "Vector diagram detected (SVG). Not processed by vision model.",
                "relevance": 0.0,
                "correctness": 0.0,
                "completeness": 0.0,
                "type": "vector_diagram"
            })
            continue

        # DUPLICATE IMAGE GUARD
        img_hash = hashlib.md5(blob).hexdigest()
        if img_hash in SEEN_IMAGE_HASHES:
            paragraphs[i] = "[IMAGE DUPLICATE – SKIPPED]"
            continue

        SEEN_IMAGE_HASHES.add(img_hash)

        try:
            vision_meta = analyze_image_semantics(blob)
            summary = vision_meta.get("brief_summary", "").strip()

            doc_meta["images"].append({
                "summary": summary,
                "relevance": vision_meta.get("relevance_score", 0.0),
                "correctness": vision_meta.get("correctness_score", 0.0),
                "completeness": vision_meta.get("completeness_score", 0.0),
                "type": vision_meta.get("image_type", "other")
            })

            paragraphs[i] = (
                "[IMAGE EVIDENCE]\n" + summary
                if summary
                else "[IMAGE PRESENT – NO SEMANTIC SUMMARY]"
            )

        except Exception:
            log.exception("Vision failed for DOCX image")
            paragraphs[i] = "[IMAGE PRESENT – VISION FAILED]"
    
    # Fallback: Process images not mapped to placeholders
    # (Handles floating images / SmartArt / grouped shapes)
    while img_idx < len(images):
        blob = images[img_idx]
        img_idx += 1

        img_hash = hashlib.md5(blob).hexdigest()
        if img_hash in SEEN_IMAGE_HASHES:
            continue

        SEEN_IMAGE_HASHES.add(img_hash)
        has_images = True
        doc_meta["images_detected"] += 1

        try:
            vision_meta = analyze_image_semantics(blob)
            summary = vision_meta.get("brief_summary", "").strip()

            doc_meta["images"].append({
                "summary": summary,
                "relevance": vision_meta.get("relevance_score", 0.0),
                "correctness": vision_meta.get("correctness_score", 0.0),
                "completeness": vision_meta.get("completeness_score", 0.0),
                "type": vision_meta.get("image_type", "other")
            })

            if summary:
                paragraphs.append("\n[IMAGE EVIDENCE]\n" + summary)
            else:
                paragraphs.append("[IMAGE PRESENT – NO SEMANTIC SUMMARY]")

        except Exception:
            log.exception("Vision fallback failed for DOCX image")

    # ---- Mark vision complete ----
    doc_meta["vision_done"] = True
    return "\n".join(paragraphs), has_images, doc_meta

# PDF — Paragraph inference helper
def _infer_paragraph_blocks_from_pdf(page) -> int:
    """
    Infer paragraph blocks using vertical gap heuristics.
    Works even when PDFs have no explicit paragraph markers.
    """

    words = page.extract_words(
        use_text_flow=True,
        keep_blank_chars=False
    )

    if not words or len(words) < 5:
        return 0

    # Sort top-to-bottom
    words.sort(key=lambda w: (w["top"], w["x0"]))

    # Collect line tops
    line_tops = []
    last_top = None

    for w in words:
        top = round(w["top"], 1)
        if last_top is None or abs(top - last_top) > 2:
            line_tops.append(top)
            last_top = top

    if len(line_tops) < 3:
        return 1

    # Compute vertical gaps
    gaps = [
        line_tops[i + 1] - line_tops[i]
        for i in range(len(line_tops) - 1)
    ]

    median_gap = median(gaps)

    # Paragraph break if gap significantly larger than normal line spacing
    paragraph_breaks = sum(
        1 for g in gaps if g > 1.6 * median_gap
    )

    return max(1, paragraph_breaks + 1)


# PDF — Inline text + PARAGRAPH INFERENCE + IMAGE DETECTION
def _extract_pdf_text_and_images_inline(
    pdf_path: str
) -> Tuple[str, bool, Dict[str, Any]]:

    text_blocks: List[str] = []
    has_images = False

    doc_meta = {
        "tables": [],
        "table_texts": [],
        "images": [],
        "images_detected": 0,
        "paragraph_blocks": 0,
        "bullet_lists": 0,
        "numbered_lists": 0
    }

    # ---------- TEXT + PARAGRAPHS (pdfplumber) ----------
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:

                # -------- TEXT --------
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    for block in re.split(r'\n{2,}', page_text):
                        cleaned = block.strip()
                        if len(cleaned.split()) >= 5:
                            text_blocks.append(cleaned)


                # -------- TABLES (NEW ATOMIC EXTRACTION) --------
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            for cell in row:
                                if not cell:
                                    continue
                                cell_text = cell.strip()
                                if len(cell_text.split()) >= 3:
                                    text_blocks.append(cell_text)

                # -------- PARAGRAPH INFERENCE --------
                para_count = _infer_paragraph_blocks_from_pdf(page)
                doc_meta["paragraph_blocks"] += para_count


    except Exception as e:
        log.error("pdfplumber text extraction failed: %s", e)

    # ---------- IMAGES (PyMuPDF) ----------
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log.error("Cannot open PDF for images: %s", e)
        return "\n".join(text_blocks), False, doc_meta

    for page in doc:
        images = page.get_images(full=True)
        if images:
            has_images = True

        for img in images:
            doc_meta["images_detected"] += 1

            base = doc.extract_image(img[0])
            img_bytes = base.get("image", None)

            if not img_bytes:
                continue

            # SVG guard
            if img_bytes.startswith(b"<svg"):
                doc_meta["images"].append({
                    "summary": "Vector diagram detected (SVG).",
                    "relevance": 0.0,
                    "correctness": 0.0,
                    "completeness": 0.0,
                    "type": "vector_diagram"
                })
                text_blocks.append("[IMAGE PRESENT – VECTOR GRAPHIC NOT ANALYZED]")
                continue

            try:
                vision_meta = analyze_image_semantics(img_bytes)

                summary = vision_meta.get("brief_summary", "").strip()
                doc_meta["images"].append({
                    "summary": summary,
                    "relevance": vision_meta.get("relevance_score", 0.0),
                    "correctness": vision_meta.get("correctness_score", 0.0),
                    "completeness": vision_meta.get("completeness_score", 0.0),
                    "type": vision_meta.get("image_type", "other")
                })

                if summary:
                    text_blocks.append("[IMAGE EVIDENCE]\n" + summary)
                else:
                    text_blocks.append("[IMAGE PRESENT – NO SEMANTIC SUMMARY]")

                if vision_meta.get("image_type") == "table":
                    doc_meta["tables"].append({
                        "rows": None,
                        "cols": None,
                        "has_header": vision_meta.get("has_data_structure", False),
                        "source": "openai_vision"
                    })

            except Exception:
                log.exception("Vision failed for PDF image")

    return "\n".join(text_blocks), has_images, doc_meta

# LOAD ASSIGNMENT
def load_assignment(full_path: str) -> Dict[str, Any]:
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"Assignment file missing: {full_path}")

    log.info("Loading assignment: %s", full_path)

    if full_path.lower().endswith(".docx"):
        doc = docx.Document(full_path)
        text, has_images, doc_meta = _extract_docx_text_inline(doc)
    else:
        text, has_images, doc_meta = _extract_pdf_text_and_images_inline(full_path)

    return {
        "text": text,
        "has_images": has_images,
        "doc_meta": doc_meta
    }


# LOAD STUDENT SUBMISSIONS
def load_student_submissions(assignment_id: str) -> Dict[str, Dict[str, Any]]:

    base = os.path.join("input_data", "students", assignment_id)
    if not os.path.isdir(base):
        raise FileNotFoundError(f"Students folder missing: {base}")

    submissions: Dict[str, Dict[str, Any]] = {}

    for student in os.listdir(base):
        student_path = os.path.join(base, student)
        if not os.path.isdir(student_path):
            continue

        docx_file = None
        pdf_file = None

        for f in os.listdir(student_path):
            fp = os.path.join(student_path, f)
            if f.lower().endswith(".docx") and docx_file is None:
                docx_file = fp
            elif f.lower().endswith(".pdf") and pdf_file is None:
                pdf_file = fp

        if not docx_file and not pdf_file:
            log.warning("No valid answer file → %s", student)
            continue

        try:
            if docx_file:
                doc = docx.Document(docx_file)
                text, has_images, doc_meta = _extract_docx_text_inline(doc)
            else:
                text, has_images, doc_meta = _extract_pdf_text_and_images_inline(pdf_file)

            submissions[student] = {
                "text": text or "",
                "has_images": has_images,
                "doc_meta": doc_meta
            }

        except Exception as e:
            log.error("Error processing %s: %s", student, e)

    return submissions