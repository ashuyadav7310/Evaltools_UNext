#scr/pipeline.py
"""
Final Evaluation Pipeline

Rules:
- Content rubrics → keypoints ONLY
- Style → heuristics only
- Format → structure only
"""

import json
import time
import torch
from typing import Dict, Any, List
from src.loader import load_assignment, load_student_submissions
from src.keypoint_loader import load_keypoints_if_any
from src.rubric_keypoint_gen import generate_keypoints_for_rubric
from src.scorer import scorer
from src.plagiarism import student_vs_student_plagiarism
from src.logging_config import get_logger
from src.model_loader import load_text_models
from src.utils import split_into_sentences

log = get_logger("pipeline")

def aggregate_image_scores(doc_meta: dict) -> dict:
    images = doc_meta.get("images", []) or []

    if not images:
        return {
            "avg_relevance": 0.0,
            "avg_correctness": 0.0,
            "avg_completeness": 0.0
        }

    return {
        "avg_relevance": sum(i.get("relevance", 0.0) for i in images) / len(images),
        "avg_correctness": sum(i.get("correctness", 0.0) for i in images) / len(images),
        "avg_completeness": sum(i.get("completeness", 0.0) for i in images) / len(images),
    }


class EvaluationPipeline:

    def __init__(self, assignment_file: str, rubric_file: str, assignment_id: str):
        self.assignment_file = assignment_file
        self.rubric_file = rubric_file
        self.assignment_id = assignment_id

        self.assignment_text: str = ""
        self.assignment_doc_meta: Dict[str, Any] = {}

        self.rubrics: List[Dict[str, Any]] = []
        self.keypoints_dict: Dict[str, List[str]] = {}

        self.all_students_text: Dict[str, Dict[str, Any]] = {}
        self.results_per_student: List[Dict[str, Any]] = []

        # Load models ONCE
        self.nlp, self.embedder, self.reranker = load_text_models()[:3]

    # Load assignment + rubrics
    def _load_assignment_and_rubrics(self):
        data = load_assignment(self.assignment_file)
        self.assignment_text = data.get("text", "")
        self.assignment_doc_meta = data.get("doc_meta", {})

        # -------- NEW: job-level rubric override --------
        rubric_path = self.rubric_file

        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load rubric file: {rubric_path}") from e

        # Support both list and wrapped formats
        self.rubrics = cfg["rubrics"] if isinstance(cfg, dict) else cfg

        for i, r in enumerate(self.rubrics, 1):
            r.setdefault("id", f"R{i}")

    # Load + Auto-generate keypoints
    def _load_keypoints(self):

        # Load DOCX keypoints (if any)
        self.keypoints_dict = load_keypoints_if_any(
            assignment_id=self.assignment_id,
            rubrics=self.rubrics
        ) or {}

        # Auto-generate missing keypoints via LLM
        for r in self.rubrics:
            if (r.get("type") or "").lower() != "content":
                continue

            if not r.get("requires_keypoints", False):
                continue
            
            rid = r["id"]
            if self.keypoints_dict.get(rid):
                continue

            log.info("Auto-generating keypoints → {}", rid)

            try:
                kps = generate_keypoints_for_rubric(
                    assignment_text=self.assignment_text,
                    rubric=r,
                    max_keypoints=6
                )
                self.keypoints_dict[rid] = kps or []
            except Exception as e:
                log.error("Keypoint generation failed → {}", e)
                self.keypoints_dict[rid] = []

    # Load students
    def _load_students(self):
        students = load_student_submissions(self.assignment_id)

        for name, entry in students.items():
            self.all_students_text[name] = {
                "text": entry.get("text", ""),
                "doc_meta": entry.get("doc_meta", {})
            }

        return students

    # Strip assignment text from student answer
    def _strip_assignment_text(self, student_text: str) -> str:
        if not student_text:
            return student_text

        assignment_sents = set(
            s.lower().strip()
            for s in split_into_sentences(self.assignment_text)
        )

        cleaned_lines = []

        for line in student_text.splitlines():
            l = line.strip()
            if not l:
                continue

            # 1. Remove questions
            if l.endswith("?"):
                continue

            # 2. Remove near-duplicate assignment sentences 
            low = l.lower()
            if any(a == low for a in assignment_sents):
                continue

            cleaned_lines.append(l)

        return "\n".join(cleaned_lines)

    # Strip rubric headings from student answer 

    def _strip_rubric_text(self, student_text: str) -> str:
        cleaned = student_text
        for r in self.rubrics:
            name = r.get("name", "")
            if name and name.isupper():  # only strip headings, not prose
                cleaned = cleaned.replace(name, "")
        return cleaned.strip()

    # Evaluate one student against all rubrics
    def _evaluate_single_student(self, sname: str, entry: Dict[str, Any]):
        raw_text = entry.get("text", "")

        # -------- NEW: Inject vision evidence into text --------
        images = entry.get("doc_meta", {}).get("images", [])

        if images:
            raw_text += "\n\n" + "\n".join(
                f"[IMAGE EVIDENCE] {img.get('summary', '')}"
                for img in images
                if img.get("summary")
            )

        table_texts = entry.get("doc_meta", {}).get("table_texts", [])

        if table_texts:
            raw_text += "\n\n[TABLE EVIDENCE]\n" + "\n".join(table_texts)


        text = self._strip_assignment_text(raw_text)
        text = self._strip_rubric_text(text)

        used_vision = entry.get("has_images", False)


        results = []
        keypoint_scores = {}

        image_scores = aggregate_image_scores(entry.get("doc_meta", {}))

        doc_meta = {
            **entry.get("doc_meta", {}),
            "assignment_paragraphs": self.assignment_doc_meta.get("paragraph_blocks", 0),
            "image_scores": image_scores
        }

        for r in self.rubrics:
            rid = r["id"]
            keypoints = self.keypoints_dict.get(rid, [])

            score, feedback, kp_matches = scorer.evaluate_rubric(
                student_answer=text,
                rubric=r,
                keypoints=keypoints,
                nlp=self.nlp,
                embedder=self.embedder,
                reranker=self.reranker,
                doc_meta=doc_meta
            )

            results.append({
                "rubric_id": rid,
                "rubric_name": r.get("name", ""),
                "rubric_type": r.get("type", ""),
                "weight": r.get("weight", 0),
                "score": score,
                "feedback": feedback,
            })

            if kp_matches:
                keypoint_scores[rid] = kp_matches

        return {
            "student_name": sname,
            "results": results,
            "keypoint_scores": keypoint_scores,
            "used_vision": used_vision,
            "answer_text": text,
            "doc_meta": {
                **entry.get("doc_meta", {}),
                "image_scores": image_scores
            }
        }

    # Run pipeline 
    def run(self):
        try:
            self._load_assignment_and_rubrics()
            self._load_keypoints()

            students = self._load_students()
            total_students = len(students)
            log.info(f"TOTAL STUDENTS TO EVALUATE: {total_students}")

            # PART A: Disable autograd globally for evaluation
            with torch.inference_mode():

                for idx, (sname, entry) in enumerate(students.items(), start=1):
                    log.info(
                        f"[STUDENT {idx}/{total_students}] STARTING evaluation → {sname}"
                    )

                    start_time = time.time()

                    result = self._evaluate_single_student(sname, entry)
                    self.results_per_student.append(result)

                    elapsed = time.time() - start_time

                    log.info(
                        "[STUDENT {}/{}] COMPLETED → {} | {:.2f}s",
                        idx,
                        total_students,
                        sname,
                        elapsed
                    )

            # Plagiarism only uses text field
            plag = student_vs_student_plagiarism(
                {
                    k: self._strip_assignment_text(v["text"])
                    for k, v in self.all_students_text.items()
                }
            )

            return self.results_per_student, plag

        except Exception as e:
            log.exception("PIPELINE CRASHED")
            return self.results_per_student, {"pairs": [], "summary_by_student": {}}
