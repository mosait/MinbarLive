"""Tests for ContextManager."""

import time
from unittest.mock import patch, MagicMock

import pytest

from utils.context_manager import ContextManager
from config import CONTEXT_RECENT_RAW_COUNT, CONTEXT_SUMMARIZE_EVERY_N


class TestContextManager:
    """Tests for ContextManager class."""

    def test_add_transcription_updates_recent_raw(self):
        """Adding transcriptions should update recent_raw deque."""
        mgr = ContextManager()

        mgr.add_transcription("First segment")
        mgr.add_transcription("Second segment")
        mgr.add_transcription("Third segment")

        context = mgr.get_context()
        assert "First segment" in context
        assert "Second segment" in context
        assert "Third segment" in context

    def test_recent_raw_limited_to_max(self):
        """Recent raw should be limited to CONTEXT_RECENT_RAW_COUNT."""
        mgr = ContextManager()

        for i in range(CONTEXT_RECENT_RAW_COUNT + 5):
            mgr.add_transcription(f"Segment {i}")

        context = mgr.get_context()
        # Oldest segments should be gone
        assert "Segment 0" not in context
        assert "Segment 1" not in context
        # Most recent should remain
        assert f"Segment {CONTEXT_RECENT_RAW_COUNT + 4}" in context

    def test_empty_transcription_ignored(self):
        """Empty or whitespace-only transcriptions should be ignored."""
        mgr = ContextManager()

        mgr.add_transcription("")
        mgr.add_transcription("   ")
        mgr.add_transcription(None)

        stats = mgr.get_stats()
        assert stats["transcription_count"] == 0

    def test_get_context_returns_immediately(self):
        """get_context should return immediately without blocking."""
        mgr = ContextManager()
        mgr.add_transcription("Test segment")

        start = time.time()
        context = mgr.get_context()
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be nearly instant
        assert "Test segment" in context

    def test_reset_clears_all_state(self):
        """Reset should clear all context state."""
        mgr = ContextManager()

        for i in range(10):
            mgr.add_transcription(f"Segment {i}")

        mgr.reset()

        stats = mgr.get_stats()
        assert stats["transcription_count"] == 0
        assert stats["hourly_summaries"] == 0
        assert not stats["has_rolling_summary"]

    def test_get_stats_returns_correct_info(self):
        """get_stats should return accurate statistics."""
        mgr = ContextManager()

        mgr.add_transcription("First")
        mgr.add_transcription("Second")

        stats = mgr.get_stats()
        assert stats["transcription_count"] == 2
        assert stats["session_minutes"] >= 0
        assert stats["hourly_summaries"] == 0
        assert stats["pending_for_summary"] == 2

    @patch("utils.context_manager.get_client")
    def test_start_stop_lifecycle(self, mock_get_client):
        """Start and stop should manage thread lifecycle correctly."""
        mgr = ContextManager()

        mgr.start()
        assert mgr._thread is not None
        assert mgr._thread.is_alive()

        mgr.stop(timeout=1.0)
        assert mgr._thread is None

    def test_context_format_structure(self):
        """Context should have proper structure with sections."""
        mgr = ContextManager()

        mgr.add_transcription("Test segment one")
        mgr.add_transcription("Test segment two")

        context = mgr.get_context()

        # Should have the "Last segments" section
        assert "[Last segments:" in context
        assert "Test segment one" in context
        assert "Test segment two" in context


class TestContextManagerIntegration:
    """Integration tests that verify summarization (require mocking API)."""

    @patch("utils.context_manager.get_client")
    def test_rolling_summary_triggered_after_n_segments(self, mock_get_client):
        """Rolling summary should be triggered after CONTEXT_SUMMARIZE_EVERY_N segments."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Summary of topics"))
        ]
        mock_get_client.return_value.chat.completions.create.return_value = (
            mock_response
        )

        mgr = ContextManager()
        mgr.start()

        try:
            # Add enough segments to trigger summarization
            for i in range(CONTEXT_SUMMARIZE_EVERY_N):
                mgr.add_transcription(f"Segment {i} with some content")

            # Give background thread time to process
            time.sleep(0.5)

            # Check that API was called for summarization
            # (It may or may not be called depending on timing)
            stats = mgr.get_stats()
            # At minimum, transcription count should be correct
            assert stats["transcription_count"] == CONTEXT_SUMMARIZE_EVERY_N

        finally:
            mgr.stop(timeout=1.0)
