import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import List

from utils.logging import log
from config import SEMANTIC_MAX_CHUNKS, SEMANTIC_MAX_SECONDS


@dataclass
class AudioSegment:
    file_path: str
    transcription: str
    is_silent: bool
    timestamp: float


class ProcessingStrategy(ABC):

    @abstractmethod
    def add_segment(self, segment: AudioSegment) -> List[str]:
        pass

    @abstractmethod
    def flush(self) -> List[str]:
        pass

    @abstractmethod
    def reset(self):
        pass


class ChunkBasedStrategy(ProcessingStrategy):

    def __init__(self):
        self.reset()

    def add_segment(self, segment: AudioSegment) -> List[str]:
        if segment.is_silent:
            return []
        return [segment.transcription] if segment.transcription.strip() else []

    def flush(self) -> List[str]:
        return []

    def reset(self):
        pass


class SemanticBufferingStrategy(ProcessingStrategy):

    def __init__(
        self,
        max_chunks: int = SEMANTIC_MAX_CHUNKS,
        max_seconds: float = SEMANTIC_MAX_SECONDS,
    ):
        self.max_chunks = max_chunks
        self.max_seconds = max_seconds
        self.reset()

    def reset(self):
        self.buffer = deque()
        self.start_time = None
        log("Semantic buffer reset", level="DEBUG")

    def _looks_semantically_complete(self, text: str) -> bool:

        text = text.strip()
        if not text:
            return False

        # Check for sentence endings (Arabic punctuation)
        if text.endswith(("؟", ".", "!", "…")):
            return True

        # Check for minimum word count
        word_count = len(text.split())
        return word_count >= 18

    def _should_flush(self) -> bool:
        if not self.buffer:
            return False

        # Timeout check
        if (
            self.start_time is not None
            and (time.time() - self.start_time) > self.max_seconds
        ):
            log(f"Semantic buffer timeout after {self.max_seconds}s", level="DEBUG")
            return True

        # Count pending non-silent segments
        pending = [
            s for s in self.buffer if not s.is_silent and s.transcription.strip()
        ]
        if len(pending) >= self.max_chunks:
            log(f"Semantic buffer max chunks reached: {len(pending)}", level="DEBUG")
            return True

        # Check semantic completeness
        buffer_text = " ".join(
            s.transcription
            for s in self.buffer
            if not s.is_silent and s.transcription.strip()
        )
        if self._looks_semantically_complete(buffer_text):
            log("Semantic buffer: text looks complete", level="DEBUG")
            return True

        return False

    def add_segment(self, segment: AudioSegment) -> List[str]:
        self.buffer.append(segment)

        if self.start_time is None:
            self.start_time = segment.timestamp

        if self._should_flush():
            return self._flush_buffer()

        return []

    def _flush_buffer(self) -> List[str]:
        if not self.buffer:
            return []

        # Combine non-silent transcriptions
        buffer_text = " ".join(
            s.transcription
            for s in self.buffer
            if not s.is_silent and s.transcription.strip()
        )

        if not buffer_text:
            # No text to translate
            self._clean_buffer()
            return []

        # Clear the entire buffer after flush - no overlap to avoid repetition
        self.buffer.clear()
        self.start_time = None

        return [buffer_text]

    def flush(self) -> List[str]:
        return self._flush_buffer()
