"""Static configuration constants and paths.

This module contains IMMUTABLE technical constants (audio params, model names,
file paths, thresholds). These are not user-configurable.

For user-configurable runtime settings (API key, language preferences, etc.),
see utils/settings.py instead.
"""

from __future__ import annotations

import os
import sys

from utils.app_paths import get_app_data_dir

# -------------------------
# AUDIO PARAMETERS
# -------------------------
# Translation mode (different languages)
DURATION = 12  # Length (in seconds) of each saved segment
OVERLAP = 3  # Overlap (in seconds) between segments
STEP = DURATION - OVERLAP  # Interval at which a new segment is captured

# Same-language mode (faster feedback, small overlap to prevent gaps)
SAME_LANG_DURATION = 5  # Shorter segments for faster feedback
SAME_LANG_OVERLAP = 1  # Small overlap to prevent missed speech
SAME_LANG_STEP = SAME_LANG_DURATION - SAME_LANG_OVERLAP  # 4 second intervals

FS = 16000  # Sample rate

# -------------------------
# MODEL CONFIGURATION
# -------------------------
# Embedding model must match the pre-built embeddings in data/embeddings/
EMBEDDING_MODEL = "text-embedding-3-large"

# -------------------------
# PATHS
# -------------------------
IS_FROZEN = bool(getattr(sys, "frozen", False))


def _get_resource_dir() -> str:
    """Directory where bundled read-only resources (like data/) live."""
    if IS_FROZEN and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


RESOURCE_DIR = _get_resource_dir()

# Bundled/static resources
DATA_DIR = os.path.join(RESOURCE_DIR, "data")
ICON_PATH = os.path.join(RESOURCE_DIR, "public", "MinbarLive.ico")
ICON_PATH_PNG = os.path.join(RESOURCE_DIR, "public", "MinbarLive1.png")

# Writable runtime data (works for EXEs, avoids Program Files permissions)
APP_DATA_DIR = str(get_app_data_dir())
AUDIO_DIR = os.path.join(APP_DATA_DIR, "recordings")
HISTORY_DIR = os.path.join(APP_DATA_DIR, "history")
LOGS_DIR = os.path.join(APP_DATA_DIR, "logs")

# Translation data directories (new structure)
TRANSLATIONS_DIR = os.path.join(DATA_DIR, "translations")
QURAN_TRANSLATIONS_DIR = os.path.join(TRANSLATIONS_DIR, "quran")
ATHAN_TRANSLATIONS_DIR = os.path.join(TRANSLATIONS_DIR, "athan")
FOOTER_TRANSLATIONS_PATH = os.path.join(TRANSLATIONS_DIR, "footer_translations.json")
GUI_TRANSLATIONS_DIR = os.path.join(TRANSLATIONS_DIR, "gui")
EMBEDDINGS_DIR = os.path.join(DATA_DIR, "embeddings")

# Embeddings path (language-agnostic, based on Arabic text)
QURAN_EMBEDDINGS_PATH = os.path.join(EMBEDDINGS_DIR, "quran_embeddings.json")


def ensure_directories() -> None:
    """Create necessary writable directories. Call this at app startup."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    # In source runs, ensure data/ exists too.
    if not IS_FROZEN:
        os.makedirs(DATA_DIR, exist_ok=True)


# -------------------------
# AUDIO BUFFER SETTINGS
# -------------------------
RING_CAPACITY = int(2 * DURATION * FS)  # Keep 2x duration in ring buffer

# -------------------------
# SEMANTIC BUFFER SETTINGS
# -------------------------
SEMANTIC_MAX_CHUNKS = 3
SEMANTIC_MAX_SECONDS = 10

# -------------------------
# SILENCE DETECTION
# -------------------------
SILENCE_THRESHOLD = 0.001
SILENCE_RATIO = 0.8

# -------------------------
# RAG SETTINGS
# -------------------------
RAG_MIN_SIMILARITY = 0.60
RAG_TOP_K = 5

# -------------------------
# DICTIONARY MATCHING
# -------------------------
ATHAN_MATCH_THRESHOLD = 0.75  # Minimum fuzzy match score for Athan detection

# -------------------------
# FILE RETENTION
# -------------------------
LOGS_RETENTION_DAYS = 30
HISTORY_RETENTION_DAYS = 90

# -------------------------
# CONTEXT MANAGEMENT
# -------------------------
CONTEXT_RECENT_RAW_COUNT = 3  # Number of recent transcriptions to keep raw
CONTEXT_SUMMARIZE_EVERY_N = 10  # Summarize after N transcriptions
CONTEXT_HOURLY_INTERVAL = 3600  # Seconds between hourly summaries

# -------------------------
# GUI SETTINGS
# -------------------------
MAX_SUBTITLES = 8
LINE_SPACING = 18
MARGIN_BOTTOM = 45
