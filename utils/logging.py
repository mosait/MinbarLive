"""Logging utilities with queue-based async logging."""

from __future__ import annotations

import queue
from datetime import datetime

# Log queue for thread-safe logging (consumed by GUI)
log_queue: queue.Queue[str] = queue.Queue()

# Log level configuration
LOG_LEVEL = "INFO"
_LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 25, "ERROR": 30}


def log(msg: str, level: str = "INFO") -> None:
    """
    Add a log message to the queue with timestamp.
    Messages below the current LOG_LEVEL are ignored.
    """
    if _LEVEL_ORDER.get(level, 20) < _LEVEL_ORDER.get(LOG_LEVEL, 20):
        return
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    log_queue.put(f"[{timestamp}] [{level}] {msg}")
