"""User-configurable runtime settings stored in user profile.

This module handles MUTABLE user preferences (API key, language, monitor index,
font size) that persist across sessions in the user's AppData directory.

For static technical constants (audio params, model names, thresholds),
see config.py instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.app_paths import get_app_data_dir

SETTINGS_FILENAME = "settings.json"

# Supported source languages (spoken language in the mosque)
# These map to ISO 639-1 codes for transcription
SOURCE_LANGUAGES = [
    ("Arabic", "ar"),
    ("German", "de"),
    ("English", "en"),
    ("Turkish", "tr"),
    ("Urdu", "ur"),
    ("Indonesian", "id"),
    ("Malay", "ms"),
    ("Persian (Farsi)", "fa"),
    ("Bengali", "bn"),
    ("Pashto", "ps"),
    ("Somali", "so"),
    ("Swahili", "sw"),
    ("Hausa", "ha"),
    ("Kurdish", "ku"),
    ("Bosnian", "bs"),
    ("Albanian", "sq"),
    ("Auto-detect", None),  # Let the model auto-detect
]

# Supported target languages for translation with ISO codes
# Format: (display_name, iso_code)
TARGET_LANGUAGES = [
    ("German", "de"),
    ("English", "en"),
    ("Arabic", "ar"),
    ("Turkish", "tr"),
    ("Albanian", "sq"),
    ("Bengali", "bn"),
    ("Bosnian", "bs"),
    ("Chinese (Simplified)", "zh-hans"),
    ("Chinese (Traditional)", "zh-hant"),
    ("Dutch", "nl"),
    ("French", "fr"),
    ("Hausa", "ha"),
    ("Hindi", "hi"),
    ("Indonesian", "id"),
    ("Italian", "it"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Kurdish", "ku"),
    ("Malay", "ms"),
    ("Pashto", "ps"),
    ("Persian (Farsi)", "fa"),
    ("Polish", "pl"),
    ("Portuguese", "pt"),
    ("Punjabi", "pa"),
    ("Russian", "ru"),
    ("Sindhi", "sd"),
    ("Somali", "so"),
    ("Spanish", "es"),
    ("Swahili", "sw"),
    ("Swedish", "sv"),
    ("Tagalog", "tl"),
    ("Tamil", "ta"),
    ("Thai", "th"),
    ("Urdu", "ur"),
    ("Vietnamese", "vi"),
]

# Helper to get target language names (for GUI dropdowns)
TARGET_LANGUAGE_NAMES = [name for name, _ in TARGET_LANGUAGES]

# Available translation models (display_name, model_id)
# Keep this list focused on practical TEXT translation models.
# Excludes image/audio/realtime/search/codex variants and legacy deprecated options.
# Organized by speed/cost: fastest first, highest quality last.
TRANSLATION_MODELS = [
    # Real-time tier (low latency)
    ("GPT-4o Mini", "gpt-4o-mini"),
    ("GPT-4.1 Mini", "gpt-4.1-mini"),
    ("GPT-5 Nano", "gpt-5-nano"),
    ("GPT-5 Mini", "gpt-5-mini"),
    # Balanced tier
    ("GPT-4o", "gpt-4o"),
    ("GPT-4.1", "gpt-4.1"),
    ("GPT-5", "gpt-5"),
    ("GPT-5.1", "gpt-5.1"),
    # Quality tier
    ("GPT-5.2 (Stable High Quality)", "gpt-5.2"),
    ("GPT-5.4 (Highest Quality)", "gpt-5.4"),
]

# Default model
DEFAULT_TRANSLATION_MODEL = "gpt-5.2"

# Fallback models to try if primary model fails (in order)
# These use the same OpenAI API, but different models may have different availability
FALLBACK_TRANSLATION_MODELS = [
    "gpt-5.2",
    "gpt-5.1",
    "gpt-4.1",
    "gpt-4o-mini",
]

# Available transcription models (display_name, model_id)
TRANSCRIPTION_MODELS = [
    ("GPT-4o Mini Transcribe (Faster & Cheaper)", "gpt-4o-mini-transcribe"),
    ("GPT-4o Transcribe (Recommended)", "gpt-4o-transcribe"),
]

# Default transcription model
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"

# Fallback transcription models to try if primary model fails (in order)
FALLBACK_TRANSCRIPTION_MODELS = [
    "gpt-4o-transcribe",
    "gpt-4o-mini-transcribe",
    "whisper-1",  # Legacy Whisper model as last resort
]


# Helper to get language code from name
def get_source_language_code(name: str) -> str | None:
    for lang_name, code in SOURCE_LANGUAGES:
        if lang_name == name:
            return code
    return None


def get_target_language_code(name: str) -> str | None:
    """Get ISO language code for a target language name."""
    for lang_name, code in TARGET_LANGUAGES:
        if lang_name == name:
            return code
    return None


# Subtitle display modes
SUBTITLE_MODE_CONTINUOUS = "continuous"  # Continuous upward scroll animation (default)
SUBTITLE_MODE_STACK = "stack"  # Stack subtitles, older ones move up (limited count)
SUBTITLE_MODE_STATIC = "static"  # Only show the most recent subtitle
SUBTITLE_MODES = [SUBTITLE_MODE_CONTINUOUS, SUBTITLE_MODE_STACK, SUBTITLE_MODE_STATIC]

# Processing strategies
PROCESSING_STRATEGIES = ["chunk", "semantic"]


# Supported GUI languages (code, display_name)
GUI_LANGUAGES = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("ar", "العربية"),
    ("bs", "Bosanski"),
    ("sq", "Shqip"),
    ("tr", "Türkçe"),
]
GUI_LANGUAGE_CODES = [code for code, _ in GUI_LANGUAGES]
DEFAULT_GUI_LANGUAGE = "de"


@dataclass
class Settings:
    # Note: openai_api_key is stored securely via keyring, not in this dataclass
    monitor_index: int = 1
    input_device_name: Optional[str] = None
    font_size_base: int = 40
    source_language: str = "Arabic"
    target_language: str = "German"
    subtitle_mode: str = SUBTITLE_MODE_CONTINUOUS  # continuous, stack, or static
    scroll_speed: float = 1.0  # Scroll speed for continuous mode (0.5 to 5.0)
    transparent_static: bool = False  # Transparent background for static mode
    window_height_percent: int = 100  # Window height as % of screen (5-100)
    translation_model: str = DEFAULT_TRANSLATION_MODEL  # OpenAI model for translation
    transcription_model: str = (
        DEFAULT_TRANSCRIPTION_MODEL  # OpenAI model for transcription
    )
    use_default_translation_model: bool = True  # Use default translation model
    use_default_transcription_model: bool = True  # Use default transcription model
    processing_strategy: str = "chunk"  # "chunk" or "semantic"
    use_default_processing_strategy: bool = True  # Use default processing strategy
    gui_language: str = DEFAULT_GUI_LANGUAGE  # GUI language (de, en)
    show_footer: bool = True  # Show footer disclaimer in subtitle window
    hide_subtitle_on_stop: bool = False  # Hide subtitle window when stopped
    adaptive_subtitle_catchup: bool = True  # Speed up display when backlog grows
    auto_cleanup: bool = True  # Purge old log/history files at startup


def _settings_path() -> Path:
    return get_app_data_dir() / SETTINGS_FILENAME


# In-memory cache to avoid repeated disk reads during translation
_cached_settings: Optional[Settings] = None


def load_settings(use_cache: bool = True) -> Settings:
    """
    Load settings from disk.

    Args:
        use_cache: If True, return cached settings if available.
                   Set to False to force a fresh read from disk.

    Returns:
        The current settings.
    """
    global _cached_settings

    if use_cache and _cached_settings is not None:
        return _cached_settings

    path = _settings_path()
    if not path.exists():
        _cached_settings = Settings()
        return _cached_settings

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Migrate old scrolling_subtitles boolean to new subtitle_mode
        subtitle_mode = data.get("subtitle_mode", None)
        if subtitle_mode is None:
            # Check for old boolean setting
            old_scrolling = data.get("scrolling_subtitles", False)
            subtitle_mode = (
                SUBTITLE_MODE_STACK if old_scrolling else SUBTITLE_MODE_STATIC
            )
        # Validate mode
        if subtitle_mode not in SUBTITLE_MODES:
            subtitle_mode = SUBTITLE_MODE_CONTINUOUS
        _cached_settings = Settings(
            monitor_index=data.get("monitor_index", 1),
            input_device_name=data.get("input_device_name"),
            font_size_base=data.get("font_size_base", 40),
            source_language=data.get("source_language", "Arabic"),
            target_language=data.get("target_language", "German"),
            subtitle_mode=subtitle_mode,
            scroll_speed=data.get("scroll_speed", 1.0),
            transparent_static=data.get("transparent_static", False),
            window_height_percent=max(
                5, min(100, data.get("window_height_percent", 100))
            ),
            translation_model=data.get("translation_model", DEFAULT_TRANSLATION_MODEL),
            transcription_model=data.get(
                "transcription_model", DEFAULT_TRANSCRIPTION_MODEL
            ),
            use_default_translation_model=data.get(
                "use_default_translation_model", True
            ),
            use_default_transcription_model=data.get(
                "use_default_transcription_model", True
            ),
            processing_strategy=data.get("processing_strategy", "chunk"),
            use_default_processing_strategy=data.get(
                "use_default_processing_strategy", True
            ),
            gui_language=data.get("gui_language", DEFAULT_GUI_LANGUAGE),
            show_footer=data.get("show_footer", True),
            hide_subtitle_on_stop=data.get("hide_subtitle_on_stop", False),
            adaptive_subtitle_catchup=data.get("adaptive_subtitle_catchup", True),
            auto_cleanup=data.get("auto_cleanup", True),
        )
        return _cached_settings
    except Exception:
        # If corrupted, fail safe: treat as empty.
        _cached_settings = Settings()
        return _cached_settings


def save_settings(settings: Settings) -> None:
    """Save settings to disk and update the cache."""
    global _cached_settings

    dir_path = _settings_path().parent
    dir_path.mkdir(parents=True, exist_ok=True)

    # Note: API key is stored securely via keyring, not in this file
    payload = {
        "monitor_index": settings.monitor_index,
        "input_device_name": settings.input_device_name,
        "font_size_base": settings.font_size_base,
        "source_language": settings.source_language,
        "target_language": settings.target_language,
        "subtitle_mode": settings.subtitle_mode,
        "scroll_speed": settings.scroll_speed,
        "transparent_static": settings.transparent_static,
        "window_height_percent": settings.window_height_percent,
        "translation_model": settings.translation_model,
        "transcription_model": settings.transcription_model,
        "use_default_translation_model": settings.use_default_translation_model,
        "use_default_transcription_model": settings.use_default_transcription_model,
        "processing_strategy": settings.processing_strategy,
        "use_default_processing_strategy": settings.use_default_processing_strategy,
        "gui_language": settings.gui_language,
        "show_footer": settings.show_footer,
        "hide_subtitle_on_stop": settings.hide_subtitle_on_stop,
        "adaptive_subtitle_catchup": settings.adaptive_subtitle_catchup,
        "auto_cleanup": settings.auto_cleanup,
    }
    tmp = _settings_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_settings_path())

    # Update the cache
    _cached_settings = settings


def get_saved_api_key() -> Optional[str]:
    """Get the API key from secure storage (keyring) or legacy settings."""
    from utils.keyring_storage import get_api_key_from_keyring, is_keyring_available

    # Try keyring first (secure storage)
    if is_keyring_available():
        key = get_api_key_from_keyring()
        if key:
            return key

    # Fallback: check for legacy key in settings file and migrate it
    path = _settings_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            legacy_key = data.get("openai_api_key")
            if legacy_key:
                # Migrate to secure storage
                set_saved_api_key(legacy_key)
                # Remove from settings file
                _remove_legacy_api_key_from_file()
                return legacy_key
        except Exception:
            pass

    return None


def _remove_legacy_api_key_from_file() -> None:
    """Remove legacy API key from settings.json after migration to keyring."""
    path = _settings_path()
    if not path.exists():
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "openai_api_key" in data:
            del data["openai_api_key"]
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(path)
    except Exception:
        pass  # Best effort cleanup


def set_saved_api_key(key: str) -> bool:
    """Save the API key to secure storage (keyring).

    Returns:
        True if stored securely, False if fell back to settings file.
    """
    from utils.keyring_storage import set_api_key_in_keyring, is_keyring_available

    key = (key or "").strip()
    if not key:
        return False

    if is_keyring_available():
        if set_api_key_in_keyring(key):
            return True

    # Fallback: store in settings file (with warning logged in keyring_storage)
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {}
        data["openai_api_key"] = key
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return False  # Stored but not securely
    except Exception:
        return False


def delete_saved_api_key() -> None:
    """Delete the API key from secure storage and any legacy location."""
    from utils.keyring_storage import delete_api_key_from_keyring, is_keyring_available

    # Delete from keyring
    if is_keyring_available():
        delete_api_key_from_keyring()

    # Also remove from settings file if present (legacy cleanup)
    _remove_legacy_api_key_from_file()
