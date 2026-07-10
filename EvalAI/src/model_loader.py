# src/model_loader.py
"""
Model Loader for Final Evaluation Pipeline, Loads the core NLP stack required for the evaluator:

  1) spaCy en_core_web_lg
  2) SentenceTransformer embedder
  3) FlagEmbedding reranker

If any model is missing → raise clear error immediately
so pipeline never crashes in the middle of evaluation.
"""

import spacy
from loguru import logger
from typing import Tuple
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker

from config.settings import (
    EMBED_MODEL,
    RERANKER_MODEL,
    DEVICE
)

def load_text_models() -> Tuple[spacy.Language, SentenceTransformer, FlagReranker]:
    """
    Returns mandatory model stack:
        nlp, embedder, reranker

    Expected usage:
        nlp, embedder, reranker = load_text_models()
    """

    # 1) spaCy
    logger.info("Loading spaCy model: en_core_web_lg")
    try:
        nlp = spacy.load("en_core_web_lg", disable=["ner"])
    except Exception:
        raise RuntimeError(
            "Missing model: en_core_web_lg\n"
            "Install using: python -m spacy download en_core_web_lg"
        )

    # 2) SentenceTransformer embedder
    logger.info(f"Loading SentenceTransformer embedder: {EMBED_MODEL} (device={DEVICE})")
    try:
        embedder = SentenceTransformer(EMBED_MODEL, device=DEVICE)
        # warm-up reduces first-time scoring latency
        embedder.encode(["warmup"], convert_to_tensor=True)
    except Exception as e:
        raise RuntimeError(
            f"ERROR loading embedding model → {EMBED_MODEL}\n{e}"
        )

    # 3) FlagEmbedding Reranker 
    logger.info(f"Loading FlagEmbedding reranker: {RERANKER_MODEL} (device={DEVICE})")
    try:
        reranker = FlagReranker(
            model_name_or_path=RERANKER_MODEL,
            device=DEVICE,
            use_fp16=(DEVICE == "cuda")
        )
    except Exception as e:
        raise RuntimeError(
            f"Reranker MUST be available but failed to load.\n"
            f"Check model id or download properly.\n"
            f"Error: {e}"
        )

    logger.info("Text model stack READY → spaCy + embedder + reranker")
    return nlp, embedder, reranker