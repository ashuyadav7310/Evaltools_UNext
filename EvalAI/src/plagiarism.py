# src/plagiarism.py
from typing import Dict, List, Tuple, Any, Union
from src.utils import normalize, split_into_sentences


# Utility function to create n-grams

def _make_ngrams(tokens: List[str], n: int):
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}

def jaccard_similarity(text_a: str, text_b: str) -> float:
    """
    Robust Jaccard n-gram similarity.
    Ensures return ∈ [0,1].
    """
    a_norm = normalize(text_a or "")
    b_norm = normalize(text_b or "")
    tokens_a = a_norm.split()
    tokens_b = b_norm.split()

    if not tokens_a or not tokens_b:
        return 0.0

    for n in (3, 2, 1):
        if len(tokens_a) >= n and len(tokens_b) >= n:
            ngrams_a = _make_ngrams(tokens_a, n)
            ngrams_b = _make_ngrams(tokens_b, n)
            if not ngrams_a or not ngrams_b:
                continue

            inter = len(ngrams_a & ngrams_b)
            union = len(ngrams_a | ngrams_b)
            return (inter / union) if union > 0 else 0.0

    return 0.0

# Student vs Student (pairwise)

def student_vs_student_plagiarism(
    students: Dict[str, Dict[str, Any]],
    top_k_matches: int = 10,
    thresholds: Tuple[float, float] = (30.0, 50.0)
) -> Dict[str, Any]:

    # Pre-normalize → sentence lists
    stu_sents = {}
    for name, entry in students.items():
        if isinstance(entry, dict):
            txt = entry.get("text", "") or entry.get("answer_text", "") or ""
        else:
            txt = str(entry or "")
        stu_sents[name] = [normalize(s) for s in split_into_sentences(txt) if s.strip()]

    names = list(stu_sents.keys())
    n = len(names)

    pairs_out = []
    summary = {
        name: {"max_similarity_pct": 0.0, "max_similarity_with": None, "flagged_pairs": []}
        for name in names
    }

    low_th, high_th = thresholds

    for i in range(n):
        for j in range(i + 1, n):
            a, b = names[i], names[j]
            sA = stu_sents[a]
            sB = stu_sents[b]

            matched = list(set(sA) & set(sB))

            sim = jaccard_similarity(" ".join(sA), " ".join(sB))
            sim_pct = round(sim * 100, 2)

            if sim_pct >= high_th:
                status = "High"
            elif sim_pct >= low_th:
                status = "Moderate"
            else:
                status = "Low"

            rec = {
                "student_a": a,
                "student_b": b,
                "score": sim_pct,
                "matches": matched[:top_k_matches],
                "status": status,
            }
            pairs_out.append(rec)

            # Update summary
            if sim_pct > summary[a]["max_similarity_pct"]:
                summary[a]["max_similarity_pct"] = sim_pct
                summary[a]["max_similarity_with"] = b
            if sim_pct > summary[b]["max_similarity_pct"]:
                summary[b]["max_similarity_pct"] = sim_pct
                summary[b]["max_similarity_with"] = a

            if sim_pct >= low_th:
                summary[a]["flagged_pairs"].append({"other": b, "sim": sim_pct})
                summary[b]["flagged_pairs"].append({"other": a, "sim": sim_pct})

    return {"pairs": pairs_out, "summary_by_student": summary}


# Wrapper expected by pipeline & output generator
def compute_pairwise_plagiarism(
    students_input: Union[
        Dict[str, Union[str, Dict[str, Any]]],
        List[Dict[str, Any]]
    ],
    top_k_matches: int = 10,
    thresholds: Tuple[float, float] = (30.0, 50.0)
) -> List[Dict[str, Any]]:

    normalized = {}

    if isinstance(students_input, dict):
        for name, val in students_input.items():
            if isinstance(val, dict):
                txt = val.get("text", "") or val.get("answer_text", "") or ""
            else:
                txt = str(val or "")
            normalized[name] = {"text": txt}

    elif isinstance(students_input, list):
        for item in students_input:
            if not isinstance(item, dict):
                continue
            name = item.get("student_name") or item.get("student") or item.get("name")
            txt = item.get("answer_text") or item.get("text") or ""
            if name:
                normalized[name] = {"text": txt}

    else:
        return []

    if len(normalized) < 2:
        return []

    result = student_vs_student_plagiarism(
        normalized,
        top_k_matches=top_k_matches,
        thresholds=thresholds
    )

    pairs = result.get("pairs", [])

    cleaned = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        p["matches"] = p.get("matches", []) or []
        cleaned.append(p)

    return cleaned
