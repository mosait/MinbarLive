"""RAG (Retrieval-Augmented Generation) for Quran verse matching using embeddings.

The embeddings are language-agnostic (based on Arabic text).
Translations are loaded dynamically based on target language.
"""

from __future__ import annotations

import os
import re
from typing import Optional

import numpy as np

from config import EMBEDDING_MODEL, QURAN_EMBEDDINGS_PATH, RAG_MIN_SIMILARITY, RAG_TOP_K
from utils.json_helpers import load_json
from utils.logging import log
from utils.openai_client import get_client
from utils.settings import get_target_language_code, load_settings
from translation.dictionary import quran_dict, get_quran_dict, has_quran_translation


def _extract_ayah_reference(translation: str) -> str:
    """
    Extract the (surah:ayah) reference from the translation text.

    Args:
        translation: Translation text that may contain (X:Y) pattern.

    Returns:
        The reference string like "(2:255)" or empty string if not found.
    """
    match = re.search(r"\((\d+:\d+)\)\s*$", translation)
    if match:
        return f"({match.group(1)})"
    return ""


def _load_and_validate_embeddings() -> dict:
    """Load and validate the Quran embeddings file."""
    if not os.path.exists(QURAN_EMBEDDINGS_PATH):
        log(
            f"Quran embeddings file not found: {QURAN_EMBEDDINGS_PATH}",
            level="WARNING",
        )
        log("RAG-based Quran matching will be disabled.", level="WARNING")
        return {}

    embeddings = load_json(QURAN_EMBEDDINGS_PATH)

    if not embeddings:
        log(
            "Quran embeddings file is empty. RAG matching disabled.",
            level="WARNING",
        )
        return {}

    # Validate structure: check first entry has valid embedding
    first_key = next(iter(embeddings))
    first_val = embeddings[first_key]

    if not isinstance(first_val, list) or len(first_val) < 100:
        log(
            f"Invalid embedding format in {QURAN_EMBEDDINGS_PATH}",
            level="ERROR",
        )
        return {}

    # Check coverage against quran_dict
    missing = sum(1 for ar in quran_dict if ar not in embeddings)
    if missing > 0:
        log(
            f"{missing}/{len(quran_dict)} Quran verses missing embeddings.",
            level="WARNING",
        )

    log(f"Loaded {len(embeddings)} Quran embeddings.", level="INFO")
    return embeddings


# Load precomputed Quran embeddings with validation (read-only after load)
quran_embeddings = _load_and_validate_embeddings()

# Flag indicating whether RAG is available (for graceful degradation)
RAG_AVAILABLE = bool(quran_embeddings)


def is_rag_available() -> bool:
    """Check if RAG-based Quran matching is available."""
    return RAG_AVAILABLE


def get_text_embedding(text: str) -> np.ndarray:
    """
    Get embedding for arbitrary text from OpenAI API.

    Args:
        text: Text to embed.

    Returns:
        Embedding as numpy float32 array.
    """
    text = (text or "").strip()
    if not text:
        return np.zeros(1, dtype=np.float32)

    try:
        resp = get_client().embeddings.create(model=EMBEDDING_MODEL, input=[text])
        emb = np.array(resp.data[0].embedding, dtype=np.float32)
        return emb
    except Exception as e:
        log(f"ERROR get_text_embedding: {e}", level="ERROR")
        return np.zeros(1, dtype=np.float32)


def get_quran_embedding(arabic_verse: str) -> np.ndarray:
    """
    Get the precomputed embedding for a Quran verse.

    Args:
        arabic_verse: Arabic text of the verse.

    Returns:
        Embedding as numpy float32 array, or zero vector if not found.
    """
    cached = quran_embeddings.get(arabic_verse)
    if cached is not None:
        return np.array(cached, dtype=np.float32)

    log(
        f"MISSING EMBEDDING for verse (not in quran_embeddings.json): '{arabic_verse[:50]}...'",
        level="ERROR",
    )
    return np.zeros(1, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.
    """
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)


def match_quran_rag_multi(
    text: str,
    min_similarity: Optional[float] = None,
    top_k: Optional[int] = None,
    target_lang_code: Optional[str] = None,
) -> list:
    """
    RAG matching for Quran verses:
    - Embed the input text
    - Compare against all Quran verse embeddings using cosine similarity
    - Return top matches above threshold with translations in target language

    Args:
        text: Arabic text to match.
        min_similarity: Minimum similarity score (default: RAG_MIN_SIMILARITY).
        top_k: Maximum number of matches to return (default: RAG_TOP_K).
        target_lang_code: Target language code for translations.
                         If None, uses current settings.
                         For 'ar', returns Arabic verse as translation.

    Returns:
        List of (score, arabic_verse, translation) tuples, sorted by score.
    """
    if min_similarity is None:
        min_similarity = RAG_MIN_SIMILARITY
    if top_k is None:
        top_k = RAG_TOP_K
    if target_lang_code is None:
        target_lang_code = (
            get_target_language_code(load_settings().target_language) or "de"
        )

    txt = (text or "").strip()
    if not txt or not quran_dict:
        return []

    query_emb = get_text_embedding(txt)
    if query_emb.size <= 1:
        return []

    # Get translation dict for target language (fallback to German for reference)
    target_dict = (
        get_quran_dict(target_lang_code)
        if has_quran_translation(target_lang_code)
        else None
    )

    matches = []

    # Use Arabic keys from default dict for matching (embeddings are based on Arabic)
    for ar in quran_dict.keys():
        verse_emb = get_quran_embedding(ar)
        if verse_emb.size <= 1:
            continue
        score = cosine_similarity(query_emb, verse_emb)
        if score >= min_similarity:
            # For Arabic target, return the Arabic verse itself
            if target_lang_code == "ar":
                trans = ar
            # For other languages, try target language, fallback to German
            elif target_dict and ar in target_dict:
                trans = target_dict[ar]
            else:
                trans = quran_dict.get(ar, ar)  # German or Arabic fallback

            matches.append((score, ar, trans))

    # Sort by score descending and limit to top_k
    matches.sort(key=lambda x: x[0], reverse=True)
    matches = matches[:top_k]

    for score, ar, trans in matches:
        ayah_ref = _extract_ayah_reference(trans)
        log(
            f"Quran-RAG match: Score={score:.3f} {ayah_ref} | AR='{ar[:40]}...'",
            level="INFO",
        )

    return matches
