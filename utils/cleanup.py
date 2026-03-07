"""File retention cleanup for logs and history directories."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta

from config import (
    HISTORY_DIR,
    HISTORY_RETENTION_DAYS,
    LOGS_DIR,
    LOGS_RETENTION_DAYS,
)
from utils.logging import log

# Matches filenames like 2026-03-07.log or 2026-03-07.txt
_DATE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\w+$")


def _purge_old_files(directory: str, retention_days: int) -> int:
    """Delete files older than *retention_days* based on the date in the filename.

    Only files whose name matches ``YYYY-MM-DD.<ext>`` are considered.
    Returns the number of files deleted.
    """
    if not os.path.isdir(directory):
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = 0

    for filename in os.listdir(directory):
        match = _DATE_PATTERN.match(filename)
        if not match:
            continue
        try:
            file_date = datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            continue

        if file_date < cutoff:
            try:
                os.remove(os.path.join(directory, filename))
                deleted += 1
            except OSError as e:
                log(f"Cleanup: failed to delete {filename}: {e}", level="WARNING")

    return deleted


def run_cleanup() -> None:
    """Purge stale log and history files. Safe to call at every startup."""
    logs_removed = _purge_old_files(LOGS_DIR, LOGS_RETENTION_DAYS)
    history_removed = _purge_old_files(HISTORY_DIR, HISTORY_RETENTION_DAYS)

    if logs_removed or history_removed:
        log(
            f"Cleanup: removed {logs_removed} log(s), {history_removed} history file(s)",
            level="INFO",
        )
