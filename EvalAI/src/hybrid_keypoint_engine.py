# src/hybrid_keypoint_engine.py

from typing import List, Dict, Any
import numpy as np
import torch
from sentence_transformers import util
from src.alignment import align_sentences
from src.utils import batch_encode, sigmoid, normalize, split_into_sentences
from config.settings import DEVICE

# --- Hyperparameters --- FOR CASE STUDY TUNED
HYBRID_FULL_THRESHOLD = 0.66
HYBRID_PARTIAL_THRESHOLD = 0.43

#--- Hyperparameters --- GENERIC qUES/ANS
#HYBRID_FULL_THRESHOLD = 0.85
#HYBRID_PARTIAL_THRESHOLD = 0.70

#--- Hyperparameters --- PPT
#HYBRID_FULL_THRESHOLD = 0.86 #change to 0.82
#HYBRID_PARTIAL_THRESHOLD = 0.74 #change to 0.72

# top-k sentences from student answer for reranking
TOP_K = 3
# weighting between cosine similarity and reranker
W_COS = 0.6
W_RERANK = 0.4
# semantic score contribution for overall relevance
SEMANTIC_WEIGHTAGE = 10.0
# gamma exponent to sharpen similarity curve
GAMMA = 1.25

_KP_EMB_CACHE = {} #Avoid recomputing keypoint embeddings
_ANSWER_EMB_CACHE = {} #Avoid recomputing full-answer embeddings

def semantic_marks(similarity: float,
                   gamma: float = GAMMA,
                   weight: float = SEMANTIC_WEIGHTAGE) -> float:
    s = max(0.0, min(float(similarity), 1.0))
    return round((s ** gamma) * weight, 2)

def safe_rerank(reranker, pairs):
    """
    Reranker wrapper (FlagEmbedding).
    pairs: list[[query, candidate], ...]
    Returns: list[float] logits (same length as clean pairs) or [] on failure
    """
    clean = []
    for p in pairs:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        a, b = normalize(p[0]), normalize(p[1])
        if a and b:
            clean.append([a, b])

    if not clean or reranker is None:
        return []

    try:
        with torch.no_grad():
            logits = reranker.compute_score(clean)
        return [float(x) for x in logits]
    except Exception:
        # any failure in reranker should not break the hybrid scorer
        return []


def _to_torch(x: np.ndarray, device: str):
    """
    Helper to convert numpy arrays to torch tensors on the specified device.
    Ensures dtype float32.
    """
    if not isinstance(x, np.ndarray):
        x = np.asarray(x, dtype=np.float32)
    if x.dtype != np.float32:
        x = x.astype(np.float32)
    try:
        t = torch.from_numpy(x)
        if device and device != "cpu":
            t = t.to(device)
        return t
    except Exception:
        # Fallback: create tensor directly
        return torch.tensor(x, dtype=torch.float32, device=(device if device else "cpu"))


def score_keypoint_content(
    answer_text: str,
    keypoints: List[str],
    nlp,
    embedder,
    reranker,
    weight: float,
    device: str = DEVICE,
) -> Dict[str, Any]:
    """
    Hybrid keypoint + semantic coverage scoring.

    Inputs:
        answer_text : full long-form student answer (string)
        keypoints   : list of key phrases (all equally weighted)
        nlp         : spaCy model (optional)
        embedder    : SentenceTransformer model (REQUIRED)
        reranker    : FlagReranker model (can be None → falls back to cosine only)
        weight      : rubric weight (max marks)
        device      : "cpu" or "cuda"

    Returns dict:
        {
          "score": float,                   # final marks out of rubric weight
          "feedback": str,                  # short technical summary
          "kp_matches": List[dict]          # list of keypoint match dicts
          "keyword_0_10": float,            # scaled keyword coverage score (0–10)
          "semantic_0_10": float,           # semantic relevance score (0–10)
          "raw_0_20": float                 # unscaled sum of keyword + semantic (0–20)
        }
    """

    # Basic validation
    answer_text = (answer_text or "").strip()
    if not embedder:
        return {
            "score": 0.0,
            "feedback": "Embedder missing; cannot compute keypoint scoring.",
            "kp_matches": []
        }

    if not answer_text or not keypoints:
        return {
            "score": 0.0,
            "feedback": "No keypoint-based content detected.",
            "kp_matches": []
        }

    # Sentence segmentation and normalization
    sents = split_into_sentences(answer_text)
    if not sents:
        sents = [answer_text]

    s_norm = [normalize(s) for s in sents if s and s.strip()]
    if not s_norm:
        return {
            "score": 0.0,
            "feedback": "No usable sentences found in student answer.",
            "kp_matches": []
        }

    # REMOVE QUESTION / PROMPT SENTENCES FROM CANDIDATE POOL
    # Prevent keypoints matching assignment questions instead of answers
    filtered_sents = []

    for s in s_norm:
        s_low = s.lower().strip()

        # Heuristic 1: explicit questions
        if s_low.endswith("?"):
            continue

        # Heuristic 2: prompt-style sentence starters
        if s_low.startswith((
            "what ", "why ", "how ", "describe ",
            "explain ", "discuss ", "outline ",
            "identify ", "list "
        )):
            continue

        # Heuristic 3: very short instructional lines
        if len(s_low.split()) <= 6:
            continue

        filtered_sents.append(s)

    # Fallback: never allow empty candidate pool
    if filtered_sents:
        s_norm = filtered_sents

    # Clean and prepare keypoints
    kp_list = [kp.strip() for kp in keypoints if kp and kp.strip()]
    if not kp_list:
        return {
            "score": 0.0,
            "feedback": "Keypoints list is empty after cleaning.",
            "kp_matches": []
        }

    # Embeddings (use provided embedder)
    try:
        s_embs = batch_encode(embedder, s_norm, device=device)

        kp_key = tuple(kp_list)
        kp_embs = _KP_EMB_CACHE.get(kp_key)
        if kp_embs is None:
            kp_embs = batch_encode(embedder, kp_list, device=device)
            _KP_EMB_CACHE[kp_key] = kp_embs

    except Exception as e:
        return {
            "score": 0.0,
            "feedback": f"Embedding failed: {e}",
            "kp_matches": []
        }

    # Ensure numpy arrays and dtype
    s_embs = np.asarray(s_embs, dtype=np.float32)
    kp_embs = np.asarray(kp_embs, dtype=np.float32)

    if s_embs.size == 0 or kp_embs.size == 0:
        return {
            "score": 0.0,
            "feedback": "Embeddings empty — cannot compute similarity.",
            "kp_matches": []
        }

    # Convert to torch tensors on device
    try:
        t_kp = _to_torch(kp_embs, device)
        t_s  = _to_torch(s_embs, device)
    except Exception:
        # as a fallback, use cpu tensors
        t_kp = torch.from_numpy(kp_embs.astype(np.float32))
        t_s  = torch.from_numpy(s_embs.astype(np.float32))

    # cosine similarity matrix: [num_kp x num_sents]
    with torch.no_grad():
        sims_tensor = util.pytorch_cos_sim(t_kp, t_s)
    # Move to CPU and numpy for indexing
    sims = sims_tensor.cpu().numpy()

    kp_matches = []
    total_keyword_awarded = 0.0
    max_possible = float(len(kp_list)) if kp_list else 0.0

    # Keypoint loop: find best matching sentence for each keypoint 
    for i, kp in enumerate(kp_list):
        kp_max = 1.0
        row = sims[i] if (sims.size and i < sims.shape[0]) else np.array([0.0] * len(s_norm))

        k = min(TOP_K, len(row))
        if k > 0:
            idx = list(np.argsort(row)[::-1][:k])
            candidates = [s_norm[j] for j in idx]
            cos_vals = [float(row[j]) for j in idx]
        else:
            candidates, cos_vals = [], []

        # prepare reranker inputs
        pair_inputs = [[kp, c] for c in candidates]
        rerank_logits = []
        if max(cos_vals, default=0.0) >= 0.35:
            rerank_logits = safe_rerank(reranker, pair_inputs)

        best_sentence = None
        best_score = 0.0

        for j, cand in enumerate(candidates):
            cos_raw = cos_vals[j]
            cos_norm = (cos_raw + 1.0) / 2.0  # map [-1,1]→[0,1]

            # Use reranker confidence only if available for this candidate
            rerank_conf = None
            if rerank_logits and j < len(rerank_logits):
                try:
                    rerank_conf = sigmoid(float(rerank_logits[j]))
                except Exception:
                    rerank_conf = None

            hybrid = cos_norm if rerank_conf is None else (W_COS * cos_norm + W_RERANK * rerank_conf)

            if hybrid > best_score:
                best_score = hybrid
                best_sentence = cand

        hybrid_score = float(best_score)

        if hybrid_score >= HYBRID_FULL_THRESHOLD:
            coverage = "full"
            awarded = kp_max
        elif hybrid_score >= HYBRID_PARTIAL_THRESHOLD:
            coverage = "partial"
            awarded = round(kp_max * hybrid_score, 4)
        else:
            coverage = "none"
            awarded = 0.0
            best_sentence = None  # treat as no match

        # Alignment (spaCy-based) for auditing
        if best_sentence and nlp is not None:
            try:
                alignment_text = align_sentences(kp, best_sentence, nlp)
            except Exception:
                alignment_text = "Alignment failed"
        else:
            alignment_text = "No alignment"

        total_keyword_awarded += awarded
        kp_matches.append({
            "keypoint": kp,
            "matched_sentence": best_sentence or "",
            "similarity": round(hybrid_score, 4),
            "coverage": coverage,
            "alignment": alignment_text
        })

    # Semantic relevance score (0–10)
    try:
        ans_key = hash(answer_text)
        ans_emb = _ANSWER_EMB_CACHE.get(ans_key)
        if ans_emb is None:
            ans_emb = batch_encode(embedder, [answer_text], device=device)[0]
            _ANSWER_EMB_CACHE[ans_key] = ans_emb

        combined_kp_emb = batch_encode(embedder, [" ".join(kp_list)], device=device)[0]
    except Exception:
        ans_emb = None
        combined_kp_emb = None

    if ans_emb is None or combined_kp_emb is None:
        base_sem = 0.0
    else:
        t_ans = _to_torch(np.asarray(ans_emb, dtype=np.float32), device)
        t_comb = _to_torch(np.asarray(combined_kp_emb, dtype=np.float32), device)
        with torch.no_grad():
            sim_kp = float(util.pytorch_cos_sim(t_ans, t_comb).item())
        sim_kp_norm = (sim_kp + 1.0) / 2.0
        base_sem = semantic_marks(sim_kp_norm)

    coverage_ratio = (total_keyword_awarded / max_possible) if max_possible > 0 else 0.0

    if coverage_ratio == 0.0:
        sem_score = 0.0
    elif coverage_ratio <= 0.30:
        sem_score = min(base_sem, 4.0)
    elif coverage_ratio <= 0.60:
        sem_score = min(base_sem, 6.0)
    else:
        sem_score = min(base_sem, 10.0)

    # Keyword coverage scaled 0–10
    scaled_keyword = (total_keyword_awarded / max_possible) * 10.0 if max_possible > 0 else 0.0
    scaled_keyword = min(scaled_keyword, 10.0)

    total_0_to_20 = round(scaled_keyword + sem_score, 2)

    # Final marks out of rubric weight
    final_marks = round((total_0_to_20 / 20.0) * float(weight), 2)

    # Feedback
    covered_count = sum(1 for m in kp_matches if m.get("coverage") == "full")
    partial_count = sum(1 for m in kp_matches if m.get("coverage") == "partial")
    missed_count = sum(1 for m in kp_matches if m.get("coverage") == "none")

    feedback = (
        f"Keypoint coverage={scaled_keyword:.1f}/10, "
        f"semantic relevance={sem_score:.1f}/10. "
        f"Full={covered_count}, partial={partial_count}, missed={missed_count}."
    )

    return {
        "score": final_marks,
        "feedback": feedback,
        "kp_matches": kp_matches,
        "keyword_0_10": round(scaled_keyword, 2),
        "semantic_0_10": round(sem_score, 2),
        "raw_0_20": total_0_to_20,
    }