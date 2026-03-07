"""Tests for file retention cleanup."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.cleanup import _purge_old_files, run_cleanup


@pytest.fixture()
def tmp_dir(tmp_path):
    """Return an empty temp directory path as a string."""
    return str(tmp_path)


def _create_dated_file(directory: str, date: datetime, ext: str = "log") -> str:
    """Create an empty file named YYYY-MM-DD.<ext> and return its path."""
    name = date.strftime("%Y-%m-%d") + f".{ext}"
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write("content")
    return path


class TestPurgeOldFiles:
    """Tests for _purge_old_files."""

    def test_deletes_files_older_than_retention(self, tmp_dir):
        today = datetime.now()
        old = today - timedelta(days=40)
        _create_dated_file(tmp_dir, old)

        deleted = _purge_old_files(tmp_dir, retention_days=30)

        assert deleted == 1
        assert len(os.listdir(tmp_dir)) == 0

    def test_keeps_files_within_retention(self, tmp_dir):
        today = datetime.now()
        recent = today - timedelta(days=5)
        _create_dated_file(tmp_dir, recent)

        deleted = _purge_old_files(tmp_dir, retention_days=30)

        assert deleted == 0
        assert len(os.listdir(tmp_dir)) == 1

    def test_keeps_file_exactly_at_boundary(self, tmp_dir):
        """A file whose date equals the cutoff date should NOT be deleted."""
        cutoff_date = datetime.now() - timedelta(days=30)
        # File date is same day as cutoff — its datetime is midnight,
        # cutoff is now()-30d which is later in the day, so file_date < cutoff.
        # We test one day *inside* the boundary to be unambiguous.
        safe_date = datetime.now() - timedelta(days=29)
        _create_dated_file(tmp_dir, safe_date)

        deleted = _purge_old_files(tmp_dir, retention_days=30)

        assert deleted == 0
        assert len(os.listdir(tmp_dir)) == 1

    def test_ignores_non_dated_files(self, tmp_dir):
        """Files that don't match YYYY-MM-DD pattern are left alone."""
        path = os.path.join(tmp_dir, "readme.txt")
        with open(path, "w") as f:
            f.write("keep me")

        deleted = _purge_old_files(tmp_dir, retention_days=0)

        assert deleted == 0
        assert os.path.exists(path)

    def test_handles_missing_directory(self):
        deleted = _purge_old_files("/nonexistent/path", retention_days=30)
        assert deleted == 0

    def test_mixed_old_and_new_files(self, tmp_dir):
        today = datetime.now()
        _create_dated_file(tmp_dir, today - timedelta(days=100))
        _create_dated_file(tmp_dir, today - timedelta(days=50), ext="txt")
        _create_dated_file(tmp_dir, today - timedelta(days=10))
        _create_dated_file(tmp_dir, today - timedelta(days=2), ext="txt")

        deleted = _purge_old_files(tmp_dir, retention_days=30)

        assert deleted == 2
        assert len(os.listdir(tmp_dir)) == 2


class TestRunCleanup:
    """Tests for run_cleanup entry point."""

    def test_run_cleanup_calls_purge_for_both_dirs(self, tmp_dir):
        logs_dir = os.path.join(tmp_dir, "logs")
        history_dir = os.path.join(tmp_dir, "history")
        os.makedirs(logs_dir)
        os.makedirs(history_dir)

        today = datetime.now()
        _create_dated_file(logs_dir, today - timedelta(days=60))
        _create_dated_file(history_dir, today - timedelta(days=120), ext="txt")

        with patch("utils.cleanup.LOGS_DIR", logs_dir), patch(
            "utils.cleanup.HISTORY_DIR", history_dir
        ), patch("utils.cleanup.LOGS_RETENTION_DAYS", 30), patch(
            "utils.cleanup.HISTORY_RETENTION_DAYS", 90
        ):
            run_cleanup()

        assert len(os.listdir(logs_dir)) == 0
        assert len(os.listdir(history_dir)) == 0

    def test_run_cleanup_keeps_recent_files(self, tmp_dir):
        logs_dir = os.path.join(tmp_dir, "logs")
        history_dir = os.path.join(tmp_dir, "history")
        os.makedirs(logs_dir)
        os.makedirs(history_dir)

        today = datetime.now()
        _create_dated_file(logs_dir, today - timedelta(days=5))
        _create_dated_file(history_dir, today - timedelta(days=10), ext="txt")

        with patch("utils.cleanup.LOGS_DIR", logs_dir), patch(
            "utils.cleanup.HISTORY_DIR", history_dir
        ), patch("utils.cleanup.LOGS_RETENTION_DAYS", 30), patch(
            "utils.cleanup.HISTORY_RETENTION_DAYS", 90
        ):
            run_cleanup()

        assert len(os.listdir(logs_dir)) == 1
        assert len(os.listdir(history_dir)) == 1
