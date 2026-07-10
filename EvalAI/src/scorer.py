# src/scorer.py
"""Scoring engine for case study evaluation.
ARCHITECTURE RULES FOR SCORER:
- Content scoring → ONLY via keypoints 
- Style scoring → Heuristics only 
- Format scoring → Structural rules only 
"""

from typing import Dict, List, Tuple, Optional
import re
import os
import json
from collections import Counter
from openai import OpenAI
from src.hybrid_keypoint_engine import score_keypoint_content
from src.utils import normalize, split_into_sentences
from src.logging_config import get_logger
from src.format_evidence import score_table_depth
from src.email_parser import extract_email_features


log = get_logger("scorer")
_llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class Scorer:

    def __init__(self):
        pass

    # FORMAT RUBRIC (STRUCTURE + VISUAL EVIDENCE ONLY)
    def score_format(
        self,
        student_answer: str,
        rubric: Dict,
        doc_meta: Dict
    ) -> Tuple[float, str, None]:

        weight = float(rubric.get("weight", 0.0))
        score = 0.0
        feedback = []

        # Paragraph structure
        p = doc_meta.get("paragraph_blocks", 0)
        if p >= 25:
            score += 0.4
            feedback.append(f"{p} paragraph blocks detected.")
        elif p >= 12:
            score += 0.35
            feedback.append(f"{p} paragraph blocks detected.")
        elif p >= 5:
            score += 0.25
            feedback.append(f"{p} paragraph blocks detected.")
        else:
            score += 0.1
            feedback.append(f"Only {p} paragraph blocks detected.")
        
        # Lists
        lists = doc_meta.get("bullet_lists", 0) + doc_meta.get("numbered_lists", 0)
        if lists > 0:
            score += 0.2
            feedback.append(f"{lists} list structures detected.")
        
        # Tables
        table_scores = [
            score_table_depth(t)
            for t in doc_meta.get("tables", [])
        ]
        if table_scores:
            avg_table = sum(table_scores) / len(table_scores)
            score += 0.25 * avg_table
            feedback.append(f"{len(table_scores)} tables with structured depth.")
        if len(doc_meta.get("tables", [])) >= 1:
            score += 0.1

        # Images
        image_count = doc_meta.get("images_detected", 0)
        if image_count > 0:
            score += 0.1
            feedback.append(f"{image_count} images detected.")

        
        image_completeness = doc_meta.get("image_scores", {}).get("avg_completeness", 0.0)

        if image_completeness > 0:
            score += min(0.2, image_completeness * 0.2)

        if image_completeness > 0:
            feedback.append(
                f"Images appear structurally complete (completeness={image_completeness:.2f})."
            )


        score = min(score, 1.0)
        return round(score * weight, 2), " ".join(feedback), None

    # STYLE RUBRIC (TEXTUAL CLARITY ONLY)
    def score_style(
        self,
        student_answer: str,
        rubric: Dict,
        doc_meta=None
    ) -> Tuple[float, str, None]:
        

        feedback = ""
        weight = float(rubric.get("weight", 0.0))
        text = normalize(student_answer)

        if not text:
            return 0.0, "No content provided.", None

        sentences = split_into_sentences(text)
        if not sentences:
            return 0.0, "No valid sentences detected.", None

        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        long_ratio = sum(1 for s in sentences if len(s.split()) >= 30) / len(sentences)
        redundancy = self._redundancy(text)
        contractions = self._contractions(text)

        score = 1.0

        para_blocks = doc_meta.get("paragraph_blocks", 0) if doc_meta else 0

        if para_blocks < 5:
            score -= 0.25
        elif 5 <= para_blocks <= 15:
            score -= 0.10
        elif 16 <= para_blocks <= 40:
            pass
        elif 41 <= para_blocks <= 80:
            score -= 0.05
        else:
            score -= 0.15


        if 12 <= avg_len <= 20:
            score += 0.05
        elif avg_len < 9 or avg_len > 28:
            score -= 0.1

        image_correctness = doc_meta.get("image_scores", {}).get("avg_correctness", 0.0)
        if image_correctness > 0:
            score *= (0.85 + 0.15 * image_correctness)
        if image_correctness > 0:
            feedback += f" Diagram correctness supported clarity (correctness={image_correctness:.2f})."


        score -= long_ratio * 0.35
        score -= redundancy * 0.35
        score -= min(0.25, contractions * 0.05)

        score = max(0.0, min(1.0, score))
        marks = round(score * weight, 2)

        feedback = (
            f"Avg sentence length={avg_len:.1f}. "
            f"Long sentence ratio={long_ratio:.2f}. "
            f"Redundancy={redundancy:.2f}. "
            f"Contractions={contractions}."
        )

        return marks, feedback, None
  
    # CONTENT RUBRIC (KEYPOINT-ONLY)
    def score_content(
        self,
        student_answer: str,
        rubric: Dict,
        keypoints: List[str],
        nlp,
        embedder,
        reranker,
        doc_meta: Optional[Dict] = None
    ) -> Tuple[float, str, Optional[List]]:

        if not keypoints:
            log.warning("Content rubric without keypoints → score = 0")
            return 0.0, "No keypoints provided for this rubric.", None

        result = score_keypoint_content(
            answer_text=student_answer,
            keypoints=keypoints,
            nlp=nlp,
            embedder=embedder,
            reranker=reranker,
            weight=float(rubric.get("weight", 0.0)),
        )

        image_relevance = (
        doc_meta.get("image_scores", {}).get("avg_relevance", 0.0)
        if doc_meta else 0.0
        )

        if image_relevance > 0:
            result["score"] *= (1 + 0.15 * image_relevance)
        feedback = result.get("feedback", "")

        if image_relevance > 0:
            feedback += f" Image relevance contributed positively (relevance={image_relevance:.2f})."

        return (
            result.get("score", 0.0),
            feedback.strip(),
            result.get("kp_matches", []),
        )
    
    def score_email_format(
        self,
        student_answer: str,
        rubric: Dict,
        doc_meta=None
    ) -> Tuple[float, str, None]:

        weight = float(rubric.get("weight", 0.0))
        features = extract_email_features(student_answer)

        if not features:
            return 0.0, "No email content detected.", None

        score = 0.0
        feedback = []

        if features["subject_present"]:
            score += 0.2
        else:
            feedback.append("Missing subject line.")

        if features["greeting_present"]:
            score += 0.2
        else:
            feedback.append("Missing greeting.")

        if features["closing_present"]:
            score += 0.2
        else:
            feedback.append("Missing professional closing.")

        if features["signature_present"]:
            score += 0.2
        else:
            feedback.append("Missing signature.")

        if 1 <= features["paragraph_count"] <= 5:
            score += 0.1
        else:
            feedback.append("Paragraph structure not ideal.")

        if features["caps_ratio"] < 0.25:
            score += 0.05
        else:
            feedback.append("Too much uppercase text.")

        if features["excess_punctuation"] == 0:
            score += 0.05
        else:
            feedback.append("Excessive punctuation detected.")

        # Guard against short template-like emails scoring too high on structure alone.
        lines = [l.strip() for l in student_answer.splitlines() if l.strip()]
        structural_prefixes = ("subject:", "subject -", "subject-")
        body_lines = []
        for line in lines:
            low = line.lower()
            if low.startswith(structural_prefixes):
                continue
            if re.match(r"^(dear|hi|hello|respected)\b", low):
                continue
            if re.match(r"^(regards|best regards|sincerely|thank you|yours faithfully)\b", low):
                continue
            body_lines.append(line)

        body_word_count = len(re.findall(r"\b\w+\b", " ".join(body_lines)))
        if body_word_count < 25:
            score = max(0.0, score - 0.2)
            feedback.append("Email body is too brief for a complete professional response.")

        score = max(0.0, min(score, 1.0))
        marks = round(score * weight, 2)

        return marks, " ".join(feedback) if feedback else "Well-formatted email.", None

    def score_llm_rubric(
        self,
        student_answer: str,
        rubric: Dict,
        doc_meta=None
    ) -> Tuple[float, str, None]:
        """
        Generic LLM rubric scoring.
        Rubric definitions are fully dynamic and taken from uploaded rubrics.json.
        """
        weight = float(rubric.get("weight", 0.0))
        rubric_name = str(rubric.get("name", "")).strip()
        rubric_desc = str(rubric.get("description", "")).strip()
        rubric_text = f"{rubric_name} {rubric_desc}".lower()
        allow_greeting_comment = ("tone" in rubric_text) or ("structure" in rubric_text)
        answer_text = (student_answer or "").strip()

        if not answer_text:
            return 0.0, "No content provided.", None

        if not os.getenv("OPENAI_API_KEY"):
            return 0.0, "OPENAI_API_KEY missing. Cannot run LLM rubric evaluation.", None

        low_text = answer_text.lower()
        email_like = bool(
            re.search(r"\bsubject\s*[:\-]", low_text)
            or re.search(r"\b(dear|hi|hello|respected)\b", low_text)
            or re.search(r"\b(regards|sincerely|thanks|thank you)\b", low_text)
        )

        etiquette_rules = """
Email Etiquette Checklist:
1) Use a clear and meaningful subject line
2) Start with a professional greeting (Hi / Hello + Name)
3) Structure emails: Context -> Action -> Timeline
4) Be concise; avoid emotional or informal language
5) Respond within 24 hours (or at least acknowledge)
6) Proofread before sending (grammar, tone, attachments)
7) Use Reply All only when truly needed
8) Use CC thoughtfully; avoid unnecessary additions
9) Use BCC only when confidentiality is required
10) Add an appropriate sign-off (Regards, Thanks & Regards, etc.)
"""

        prompt = f"""
You are evaluating ONE rubric for a student submission.

Rubric Name:
{rubric_name}

Rubric Description:
{rubric_desc}

Rubric Max Score:
{weight}

Student Submission:
{answer_text[:12000]}

Return STRICT JSON only:
{{
  "score": number,
  "feedback": "rubric-specific, evidence-driven evaluation",
  "evidence_spans": ["exact quote 1", "exact quote 2", "exact quote 3"],
  "strength_note": "one concrete strength tied to rubric",
  "improvement_note": "one concrete issue tied to rubric with corporate writing expectation",
  "rewrite_tip": "one actionable rewrite suggestion",
  "etiquette_feedback": "one concise sentence for this rubric using only relevant etiquette rules",
  "applied_etiquette_rule_ids": [1, 3]
}}

Rules:
- Score must be between 0 and {weight}.
- Use only evidence from the student submission.
- Be strict and consistent with professional evaluation.
- Feedback must prioritize the current rubric ({rubric_name}).
- If submission is email-like ({email_like}), consider all 10 etiquette rules internally.
- Do NOT list all 10 rules in output.
- Produce only one etiquette_feedback sentence focused on rules relevant to THIS rubric.
- Choose relevant rules using only rubric name/description from user input.
- Include those chosen rule ids in applied_etiquette_rule_ids.
- Avoid generic wording like "somewhat", "mostly", "generally", "could be improved".
- Make comments phrase-level and specific to this submission.
- If greeting is non-corporate (e.g., "Good afternoon team", "Respected Sir"), call it out explicitly and suggest a corporate alternative like "Hi <Name>,", when relevant to this rubric.
- Keep rubric boundaries strict: do not repeat the same broad comment across every rubric.
- Mention greeting issues only if they are directly relevant to this rubric. Relevant now: {allow_greeting_comment}.

{etiquette_rules}
"""
        try:
            res = _llm_client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": "You evaluate rubric-based writing strictly and return valid JSON only."
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw = (res.choices[0].message.content or "").strip()
            data = json.loads(raw) if raw else {}
        except Exception as e:
            log.warning("LLM rubric evaluation failed for '%s': %s", rubric_name, e)
            return 0.0, f"LLM evaluation failed for rubric '{rubric_name}'.", None

        try:
            score = float(data.get("score", 0.0))
        except Exception:
            score = 0.0
        score = max(0.0, min(score, weight))
        score = round(score, 2)

        feedback = str(data.get("feedback", "")).strip()
        evidence = data.get("evidence_spans", [])
        if isinstance(evidence, list):
            evidence = [str(x).strip() for x in evidence if str(x).strip()][:3]
        else:
            evidence = []
        strength_note = str(data.get("strength_note", "")).strip()
        improvement_note = str(data.get("improvement_note", "")).strip()
        rewrite_tip = str(data.get("rewrite_tip", "")).strip()
        strength_note = strength_note[:180]
        improvement_note = improvement_note[:220]
        rewrite_tip = rewrite_tip[:200]

        etiquette_feedback = str(data.get("etiquette_feedback", "")).strip()
        etiquette_feedback = etiquette_feedback[:240]
        applied_rule_ids = data.get("applied_etiquette_rule_ids", [])
        clean_rule_ids = []
        if isinstance(applied_rule_ids, list):
            for rid in applied_rule_ids[:4]:
                try:
                    rid_int = int(rid)
                except Exception:
                    continue
                if 1 <= rid_int <= 10:
                    clean_rule_ids.append(rid_int)

        # Suppress repeated greeting commentary outside greeting-relevant rubrics.
        if not allow_greeting_comment:
            def _remove_greeting_sentences(text: str) -> str:
                if not text:
                    return text
                chunks = re.split(r"(?<=[.!?])\s+", text)
                kept = [
                    c for c in chunks
                    if not re.search(r"\bgreeting\b|\bhi\b|\bhello\b|\brespected sir\b|\bgood afternoon\b", c, re.I)
                ]
                return " ".join(kept).strip()

            feedback = _remove_greeting_sentences(feedback)
            strength_note = _remove_greeting_sentences(strength_note)
            improvement_note = _remove_greeting_sentences(improvement_note)
            rewrite_tip = _remove_greeting_sentences(rewrite_tip)
            etiquette_feedback = _remove_greeting_sentences(etiquette_feedback)
            #clean_rule_ids = [rid for rid in clean_rule_ids if rid != 2]

        detail_bits = []
        if strength_note:
            detail_bits.append(f"Strength: {strength_note}")
        if improvement_note:
            detail_bits.append(f"Improve: {improvement_note}")
        if rewrite_tip:
            detail_bits.append(f"Rewrite tip: {rewrite_tip}")
        if detail_bits:
            feedback = (feedback + " " + " ".join(detail_bits)).strip()

        # if evidence:
        #     feedback = (feedback + " Evidence: " + " | ".join(evidence)).strip()
        # Keep evidence in model output for grounding, but do not append it to final
        # feedback text to avoid repetitive and overly long report rows.
        if etiquette_feedback:
            if clean_rule_ids:
                feedback = (
                    feedback
                    + " Etiquette: "
                    + etiquette_feedback
                    #+ f" (rules: {','.join(str(i) for i in clean_rule_ids)})"
                ).strip()
            else:
                feedback = (feedback + " Etiquette: " + etiquette_feedback).strip()
        if not feedback:
            feedback = "LLM rubric evaluation completed."

        # Language policy: avoid "rubric/rubrics/marks" in feedback text.
        feedback = re.sub(r"\brubrics?\b", "criterion", feedback, flags=re.IGNORECASE)
        feedback = re.sub(r"\bmarks?\b", "score", feedback, flags=re.IGNORECASE)

        return score, feedback, None

    # DISPATCHER (PIPELINE-SAFE)
    def evaluate_rubric(
        self,
        student_answer: str,
        rubric: Dict,
        keypoints: Optional[List[str]] = None,
        nlp=None,
        embedder=None,
        reranker=None,
        doc_meta: Optional[Dict] = None
    ) -> Tuple[float, str, Optional[List]]:

        rtype = (rubric.get("type") or "content").lower()

        if rtype == "format":
            return self.score_format(student_answer, rubric, doc_meta or {})

        if rtype == "style":
            return self.score_style(student_answer, rubric, doc_meta)

        if rtype == "email_format":
            return self.score_email_format(student_answer, rubric, doc_meta)

        if rtype == "email":
            return self.score_llm_rubric(student_answer, rubric, doc_meta)

        if rtype == "content":
            return self.score_content(
                student_answer=student_answer,
                rubric=rubric,
                keypoints=keypoints or [],
                nlp=nlp,
                embedder=embedder,
                reranker=reranker,
                doc_meta=doc_meta
            )

        return 0.0, "Unsupported rubric type.", None


    # INTERNAL HELPERS
    def _redundancy(self, text: str, n: int = 5) -> float:
        tokens = normalize(text).split()
        if len(tokens) < n:
            return 0.0
        ngrams = [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]
        counts = Counter(ngrams)
        repeated = sum(1 for c in counts.values() if c > 1)
        return min(1.0, repeated / max(1, len(ngrams)))

    def _contractions(self, text: str) -> int:
        pats = [
            r"\bdon't\b", r"\bcan't\b", r"\bwon't\b", r"\bit's\b",
            r"\bi'm\b", r"\bwe're\b", r"\bthey're\b"
        ]
        low = text.lower()
        return sum(len(re.findall(p, low)) for p in pats)


# Singleton
scorer = Scorer()
