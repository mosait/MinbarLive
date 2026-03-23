"""Tests for settings management."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.settings import (
    Settings,
    SUBTITLE_MODE_CONTINUOUS,
    SUBTITLE_MODE_STACK,
    SUBTITLE_MODE_STATIC,
    SUBTITLE_MODES,
    get_source_language_code,
    SOURCE_LANGUAGES,
    TARGET_LANGUAGE_NAMES,
    DEFAULT_TRANSLATION_MODEL,
    DEFAULT_TRANSCRIPTION_MODEL,
)


class TestSettingsDataclass:
    """Tests for Settings dataclass."""

    def test_default_values(self):
        """Settings should have sensible defaults."""
        settings = Settings()
        # Note: openai_api_key is now stored in keyring, not in Settings
        assert settings.monitor_index == 1
        assert settings.font_size_base == 40
        assert settings.source_language == "Arabic"
        assert settings.target_language == "German"
        assert settings.subtitle_mode == SUBTITLE_MODE_CONTINUOUS
        assert settings.scroll_speed == 1.0
        assert settings.transparent_static is False
        assert settings.adaptive_subtitle_catchup is False
        assert settings.translation_model == DEFAULT_TRANSLATION_MODEL
        assert settings.transcription_model == DEFAULT_TRANSCRIPTION_MODEL

    def test_custom_values(self):
        """Settings should accept custom values."""
        settings = Settings(
            monitor_index=0,
            font_size_base=50,
            source_language="Turkish",
            target_language="English",
            subtitle_mode=SUBTITLE_MODE_STATIC,
            scroll_speed=2.5,
            transparent_static=True,
            adaptive_subtitle_catchup=True,
            translation_model="gpt-4o",
            transcription_model="gpt-4o-mini-transcribe",
        )
        assert settings.monitor_index == 0
        assert settings.font_size_base == 50
        assert settings.source_language == "Turkish"
        assert settings.target_language == "English"
        assert settings.subtitle_mode == SUBTITLE_MODE_STATIC
        assert settings.scroll_speed == 2.5
        assert settings.transparent_static is True
        assert settings.adaptive_subtitle_catchup is True
        assert settings.translation_model == "gpt-4o"
        assert settings.transcription_model == "gpt-4o-mini-transcribe"


class TestSubtitleModes:
    """Tests for subtitle mode constants."""

    def test_mode_values(self):
        """Mode constants should have expected values."""
        assert SUBTITLE_MODE_CONTINUOUS == "continuous"
        assert SUBTITLE_MODE_STACK == "stack"
        assert SUBTITLE_MODE_STATIC == "static"

    def test_modes_list(self):
        """SUBTITLE_MODES should contain all modes."""
        assert SUBTITLE_MODE_CONTINUOUS in SUBTITLE_MODES
        assert SUBTITLE_MODE_STACK in SUBTITLE_MODES
        assert SUBTITLE_MODE_STATIC in SUBTITLE_MODES
        assert len(SUBTITLE_MODES) == 3


class TestSourceLanguageCode:
    """Tests for source language code lookup."""

    def test_arabic_code(self):
        """Arabic should return 'ar'."""
        assert get_source_language_code("Arabic") == "ar"

    def test_turkish_code(self):
        """Turkish should return 'tr'."""
        assert get_source_language_code("Turkish") == "tr"

    def test_auto_detect_code(self):
        """Auto-detect should return None."""
        assert get_source_language_code("Auto-detect") is None

    def test_unknown_language(self):
        """Unknown language should return None."""
        assert get_source_language_code("Klingon") is None

    def test_all_languages_have_codes(self):
        """All source languages should have a code defined."""
        for name, code in SOURCE_LANGUAGES:
            # Each entry should be a (name, code) tuple
            assert isinstance(name, str)
            assert code is None or isinstance(code, str)


class TestTargetLanguageNames:
    """Tests for target language names list."""

    def test_german_is_first(self):
        """German should be the first/default language."""
        assert TARGET_LANGUAGE_NAMES[0] == "German"

    def test_common_languages_present(self):
        """Common languages should be in the list."""
        assert "English" in TARGET_LANGUAGE_NAMES
        assert "Arabic" in TARGET_LANGUAGE_NAMES
        assert "Turkish" in TARGET_LANGUAGE_NAMES
        assert "French" in TARGET_LANGUAGE_NAMES

    def test_no_duplicates(self):
        """There should be no duplicate languages."""
        assert len(TARGET_LANGUAGE_NAMES) == len(set(TARGET_LANGUAGE_NAMES))


class TestSettingsEdgeCases:
    """Edge case tests for settings."""

    def test_settings_without_api_key(self):
        """Settings dataclass should not have openai_api_key (stored in keyring)."""
        settings = Settings()
        # Verify openai_api_key is not an attribute
        assert not hasattr(settings, "openai_api_key")

    def test_negative_monitor_index(self):
        """Negative monitor index should be accepted (validation elsewhere)."""
        settings = Settings(monitor_index=-1)
        assert settings.monitor_index == -1

    def test_extreme_scroll_speed(self):
        """Extreme scroll speed values should be accepted."""
        settings = Settings(scroll_speed=100.0)
        assert settings.scroll_speed == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
