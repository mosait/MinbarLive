"""History logging for transcriptions and translations."""

from __future__ import annotations

import os
from datetime import datetime

from config import HISTORY_DIR
from utils.logging import log
from utils.settings import load_settings


def log_transcription_and_translation(
    transcription: str,
    translation: str,
    duration: float | None = None,
) -> None:
    """
    Log a transcription and its translation to the daily history file.

    Args:
        transcription: The original transcribed text.
        translation: The translated text.
        duration: Optional processing duration in seconds.
    """
    try:
        settings = load_settings()
        source_lang = settings.source_language[:2].upper()  # e.g., "AR", "TR", "UR"
        target_lang = settings.target_language[:2].upper()  # e.g., "DE", "EN", "FR"

        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(HISTORY_DIR, f"{date_str}.txt")
        timestamp = datetime.now().strftime("%H:%M:%S")

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {source_lang}: {transcription}\n")
            f.write(f"[{timestamp}] {target_lang}: {translation}\n")
            if duration is not None:
                f.write(f"[Processing time]: {duration:.2f}s\n")
            f.write("\n")
    except Exception as e:
        log(f"History write error: {e}", level="ERROR")
