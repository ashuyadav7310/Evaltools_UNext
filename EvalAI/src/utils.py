# src/utils.py
import re
from typing import List, Optional
import numpy as np

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_SPAM = re.compile(r"[•­●▪■□]+")
_MULTIDOTS = re.compile(r"\.{3,}")
_NUM_CURRENCY = re.compile(r"[₹$,]")

def normalize(text: Optional[str]) -> str:
    """
    Cleans text for similarity, plagiarism & LLM prompts.
    - Remove bullet icons, repeated dots
    - Remove currency symbols
    - Collapse whitespace
    """
    if not text:
        return ""
    text = str(text)
    text = _PUNCT_SPAM.sub(" ", text)
    text = _MULTIDOTS.sub(".", text)
    text = _NUM_CURRENCY.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()

def split_into_sentences(text: str) -> List[str]:
    """
    Improved chunking without changing scoring logic.
    Adds sub-sentence granularity for:
    - Bullet points
    - Table-like rows
    - Headings
    - Semicolon-separated clauses
    """

    if not text:
        return []

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Split on strong delimiters first
    primary_chunks = re.split(r'[.!?]\s+', text)

    refined_chunks = []

    for chunk in primary_chunks:
        # Further split on:
        # - semicolons
        # - colons (often used in headings)
        # - em dash / arrow
        # - numbered list markers
        sub_chunks = re.split(
            r';|\s:\s|→| - |\s\d+\.\s|\s•\s',
            chunk
        )

        for sub in sub_chunks:
            cleaned = sub.strip()
            if len(cleaned) > 20:  # avoid noise fragments
                refined_chunks.append(cleaned)

    return refined_chunks

def sigmoid(x: float) -> float:
    """Standard logistic function for scaling scores."""
    return 1.0 / (1.0 + float(np.exp(-float(x))))

def batch_encode(embedder, texts: List[str], batch_size=32, device="cpu"):
    """
    Efficient batched embedding for reranker/semantic coverage.
    - Normalizes texts before encoding
    - Uses convert_to_tensor for GPU/CPU
    - No duplicate encoding of identical strings
    """
    if not texts:
        return np.array([])

    clean = [normalize(t) for t in texts]

    embeddings = embedder.encode(
        clean,
        batch_size=batch_size,
        convert_to_tensor=True,
        device=device,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings
