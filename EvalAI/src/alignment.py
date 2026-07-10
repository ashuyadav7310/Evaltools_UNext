# src/alignment.py
"""
Sentence-to-sentence semantic alignment.
Used when a rubric is evaluated by comparing the
reference sentence (LLM-generated) with the student answer.

Works in pipeline:
  reference_sentence → student_sentence
and returns:
  "phraseA ↔ phraseB (semantic 0.82)" or "No alignment"
"""

from typing import Optional, List, Tuple
from src.logging_config import get_logger

log = get_logger("alignment")

#Checks whether a phrase has enough word vectors to compute reliable semantic similarity.
def _has_vectors(span) -> bool:  
    tokens = [t for t in span if t.is_alpha]
    if not tokens:
        return False
    return sum(t.has_vector for t in tokens) / len(tokens) >= 0.70

# Extract meaningful phrases (nouns + verbs) from a doc.
def extract_phrases(doc) -> List[str]:
    try:
        nouns = [chunk.lemma_.lower().strip() for chunk in doc.noun_chunks]
        verbs = [
            tok.lemma_.lower().strip()
            for tok in doc
            if tok.pos_ == "VERB" and not tok.is_stop and tok.is_alpha
        ]
        raw = nouns + verbs
        phrases = [p for p in raw if len(p) >= 3 and p not in {"thing", "stuff", "people"}]
        return list(dict.fromkeys(phrases))
    except Exception as e:
        log.error("extract_phrases failed: %s", e)
        return []

# Find best semantic match between two docs (reference vs student).
def _best_semantic_match(
    ref_doc, stu_doc, sim_threshold: float = 0.60
) -> Optional[Tuple[str, str, float]]:
    """
    Highest similarity noun-phrase match between reference vs student.
    """
    best = None
    try:
        for r_span in ref_doc.noun_chunks:
            if not _has_vectors(r_span):
                continue
            r_text = r_span.text.strip()
            if len(r_text) < 3:
                continue

            for s_span in stu_doc.noun_chunks:
                if not _has_vectors(s_span):
                    continue
                s_text = s_span.text.strip()
                if len(s_text) < 3:
                    continue

                sim = r_span.similarity(s_span)
                if sim >= sim_threshold and (best is None or sim > best[2]):
                    best = (r_text, s_text, sim)
                    if sim >= 0.90:
                        return best
    except Exception as e:
        log.error("_best_semantic_match failed: %s", e)

    return best

# Main function that tries to align one reference sentence with one student sentence.
def align_sentences(ref_sentence: str, stu_sentence: str, nlp) -> str:
    """
    Human-readable mapping for 1 reference sentence vs 1 student sentence.
    Priority:
      semantic match > substring phrase match > token lemma overlap
    """
    if not ref_sentence or not stu_sentence:
        return "No alignment"

    try:
        ref_doc = nlp(ref_sentence.strip())
        stu_doc = nlp(stu_sentence.strip())

        # Semantic alignment
        sem = _best_semantic_match(ref_doc, stu_doc)
        if sem:
            return f"{sem[0]} ↔ {sem[1]} (semantic {sem[2]:.2f})"

        # Substring phrase match
        r_phr = extract_phrases(ref_doc)
        s_phr = extract_phrases(stu_doc)
        for a in r_phr:
            for b in s_phr:
                if a == b:
                    return f"{a} ↔ {b} (exact)"
                if a in b and len(a) >= 3:
                    return f"{a} ↔ {b} (substr)"
                if b in a and len(b) >= 3:
                    return f"{a} ↔ {b} (substr)"

        # Token lemma overlap
        r_tok = {t.lemma_.lower() for t in ref_doc if t.has_vector and not t.is_stop and t.is_alpha}
        s_tok = {t.lemma_.lower() for t in stu_doc if t.has_vector and not t.is_stop and t.is_alpha}
        overlap = sorted(r_tok & s_tok)
        if overlap:
            return f"{', '.join(overlap)} (tokens)"
    except Exception as e:
        log.error("align_sentences failed: %s", e)

    return "No alignment"