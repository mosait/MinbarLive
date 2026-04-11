"""Thread lifecycle controller for starting/stopping the pipeline."""

from __future__ import annotations

import os
import time
import queue
import threading

import numpy as np
import scipy.io.wavfile as wavfile
import sounddevice as sd

from config import AUDIO_DIR, FS
from utils.logging import log
from utils.openai_client import get_client
from utils.retry import retry_with_backoff
from utils.settings import (
    load_settings,
    get_source_language_code,
    DEFAULT_TRANSCRIPTION_MODEL,
    FALLBACK_TRANSCRIPTION_MODELS,
)
from utils.history import log_transcription_and_translation
from utils.context_manager import get_context_manager
from audio.capture import (
    audio_callback,
    get_default_input_device,
    is_silence,
    reset_ring_buffer,
)
from audio.writer import segment_writer, async_write_audio, clear_write_queue
from translation.translator import translate_text
from translation.buffering import (
    SemanticBufferingStrategy,
    ChunkBasedStrategy,
    ProcessingStrategy,
    AudioSegment,
)


class AppController:
    def __init__(self):
        self.stop_event = threading.Event()
        self._input_stop_event = threading.Event()  # Separate stop for input stream
        self._input_thread: threading.Thread | None = None
        self._current_device: int | None = None
        self.threads: list[threading.Thread] = []
        self.translation_queue: queue.Queue[str] = queue.Queue()
        self.error_queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self.strategy: ProcessingStrategy | None = None

    def _process_audio(self):
        context_mgr = get_context_manager()
        files_processed = 0

        while not self.stop_event.is_set():
            files = sorted([f for f in os.listdir(AUDIO_DIR) if f.endswith(".wav")])

            for file in files:
                file_path = os.path.join(AUDIO_DIR, file)
                start_time = time.time()
                log(f"AUDIO-PROCESSOR File found: {file}", level="INFO")

                try:
                    _, data = wavfile.read(file_path)
                    audio_float = data.astype(np.float32) / 32767.0

                    if is_silence(audio_float):
                        log(
                            f"AUDIO-PROCESSOR Silence detected → deleted: {file}",
                            level="DEBUG",
                        )
                        os.remove(file_path)
                        continue

                    log(f"AUDIO-PROCESSOR Transcription started: {file}", level="INFO")
                    client = get_client()

                    # Get source language and transcription model from settings
                    settings = load_settings()
                    lang_code = get_source_language_code(settings.source_language)
                    primary_model = (
                        settings.transcription_model or DEFAULT_TRANSCRIPTION_MODEL
                    )

                    # Build fallback chain: primary model first, then fallbacks (deduplicated)
                    models_to_try = [primary_model]
                    for fallback in FALLBACK_TRANSCRIPTION_MODELS:
                        if fallback not in models_to_try:
                            models_to_try.append(fallback)

                    with open(file_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()

                    transcription = None
                    last_error = None
                    for model in models_to_try:
                        try:
                            log(f"Trying transcription model: {model}", level="DEBUG")
                            # Pass language hint if configured, otherwise auto-detect
                            transcribe_kwargs = {
                                "model": model,
                                "file": ("audio.wav", audio_bytes),
                                "response_format": "text",
                            }
                            if lang_code:  # None means auto-detect
                                transcribe_kwargs["language"] = lang_code

                            def _call_transcription_api():
                                return client.audio.transcriptions.create(
                                    **transcribe_kwargs
                                )

                            transcription = retry_with_backoff(
                                _call_transcription_api,
                                max_retries=2,  # Fewer retries since we have fallbacks
                                operation_name=f"Transcription ({model})",
                            )
                            break  # Success, exit loop

                        except Exception as e:
                            last_error = e
                            log(
                                f"Transcription model {model} failed: {e}",
                                level="WARNING",
                            )
                            continue  # Try next model

                    if transcription is None:
                        log(
                            f"All transcription models failed. Last error: {last_error}",
                            level="ERROR",
                        )
                        os.remove(file_path)
                        continue  # Skip this audio file

                    log(f"AUDIO-PROCESSOR Transcription received", level="DEBUG")

                    # Create AudioSegment for strategy processing
                    segment = AudioSegment(
                        file_path=file_path,
                        transcription=transcription,
                        is_silent=False,
                        timestamp=time.time(),
                    )

                    transcriptions_to_translate = self.strategy.add_segment(segment)
                    log_transcriptions = []  # To store transcription-translation pairs

                    for (
                        trans_text
                    ) in transcriptions_to_translate:  # Renamed for clarity

                        # Check if same language (skip summarization if so)
                        same_language = (
                            settings.source_language == settings.target_language
                        )

                        # Add to context manager (skip summarization for same-language mode)
                        context_mgr.add_transcription(
                            trans_text, enable_summarization=not same_language
                        )
                        context = "" if same_language else context_mgr.get_context()

                        if same_language:
                            log(f"AUDIO-PROCESSOR Same-language mode", level="INFO")
                        else:
                            log(f"AUDIO-PROCESSOR Translation started", level="INFO")
                        translation = translate_text(trans_text, context)

                        self.translation_queue.put(translation)
                        log_transcriptions.append((trans_text, translation))

                    try:
                        os.remove(file_path)
                    except Exception as e_del:
                        log(
                            f"AUDIO-PROCESSOR Delete error for {file}: {e_del}",
                            level="ERROR",
                        )

                    files_processed += 1
                    duration = time.time() - start_time
                    log(
                        f"AUDIO-PROCESSOR Processing complete in {duration:.2f}s",
                        level="INFO",
                    )

                    # Log all transcription-translation pairs
                    for trans_text, translation in log_transcriptions:
                        log_transcription_and_translation(
                            trans_text, translation, duration=duration
                        )

                except Exception as e:
                    log(f"AUDIO-PROCESSOR Error for {file}: {e}", level="ERROR")
                    # Delete file anyway to prevent buildup during network outages
                    try:
                        os.remove(file_path)
                        log(
                            f"AUDIO-PROCESSOR Deleted {file} after error", level="DEBUG"
                        )
                    except Exception:
                        pass
                    # Show connection error in subtitles
                    self.translation_queue.put("[⚠️ Verbindungsfehler]")

            time.sleep(0.2)

        if self.strategy is not None:
            remaining_transcriptions = self.strategy.flush()
            for transcription_text in remaining_transcriptions:
                settings = load_settings()
                same_language = settings.source_language == settings.target_language
                context_mgr.add_transcription(
                    transcription_text, enable_summarization=not same_language
                )
                context = "" if same_language else context_mgr.get_context()
                translation = translate_text(transcription_text, context)
                self.translation_queue.put(translation)
                log_transcription_and_translation(transcription_text, translation)

        log(f"AUDIO-PROCESSOR ended. Total processed: {files_processed}", level="INFO")

    def _input_stream_thread(self, device: int):
        try:
            with sd.InputStream(
                samplerate=FS, channels=1, callback=audio_callback, device=device
            ):
                log(f"InputStream started on device {device}", level="INFO")
                # Check both stop events - main stop or input-specific stop
                while (
                    not self.stop_event.is_set() and not self._input_stop_event.is_set()
                ):
                    time.sleep(0.1)
                log(f"InputStream stopping on device {device}", level="DEBUG")
        except OSError as e:
            log(f"Audio device error (device {device}): {e}", level="ERROR")
            self.error_queue.put(f"audio_device_lost:{device}")
        except Exception as e:
            log(f"InputStream error: {e}", level="ERROR")
            self.error_queue.put(f"input_stream_error:{e}")

    def start(self, input_device: int | None = None):
        if self._running:
            return

        self.stop_event = threading.Event()
        self._input_stop_event = threading.Event()
        self.threads = []

        # Reset shared audio state to ensure clean start
        reset_ring_buffer()
        clear_write_queue()

        # Also clear the translation and error queues
        while not self.translation_queue.empty():
            try:
                self.translation_queue.get_nowait()
            except queue.Empty:
                break
        while not self.error_queue.empty():
            try:
                self.error_queue.get_nowait()
            except queue.Empty:
                break

        # Clean up any leftover audio files from previous session
        try:
            for f in os.listdir(AUDIO_DIR):
                if f.endswith(".wav") or f.endswith(".tmp"):
                    try:
                        os.remove(os.path.join(AUDIO_DIR, f))
                    except Exception:
                        pass
        except Exception as e:
            log(f"Error cleaning up audio files: {e}", level="DEBUG")

        if input_device is None:
            input_device = get_default_input_device()

        self._current_device = input_device
        log(f"Using input device index: {input_device}", level="INFO")

        # Log the models being used
        settings = load_settings()
        log(f"Translation model: {settings.translation_model}", level="INFO")
        log(f"Transcription model: {settings.transcription_model}", level="INFO")

        # Initialize processing strategy
        if settings.processing_strategy == "semantic":
            self.strategy = SemanticBufferingStrategy()
            log("Using SEMANTIC buffering strategy", level="INFO")
        else:
            self.strategy = ChunkBasedStrategy()
            log("Using CHUNK-based strategy", level="INFO")

        self.strategy.reset()

        # Start context manager (for async summarization)
        context_mgr = get_context_manager()
        context_mgr.reset()  # Fresh context for new session
        context_mgr.start()

        # Start input stream thread (tracked separately for hot-swapping)
        self._input_thread = threading.Thread(
            target=self._input_stream_thread,
            args=(input_device,),
            daemon=True,
            name="input-stream",
        )
        self._input_thread.start()

        # Start other threads
        thread_defs = [
            (segment_writer, (self.stop_event,), "segment-writer"),
            (async_write_audio, (self.stop_event,), "audio-writer"),
            (self._process_audio, tuple(), "audio-processor"),
        ]

        for target, args, name in thread_defs:
            t = threading.Thread(target=target, args=args, daemon=True, name=name)
            self.threads.append(t)
            t.start()

        self._running = True

    def stop(self, timeout: float = 2.0):
        if not self._running:
            return

        self.stop_event.set()
        self._input_stop_event.set()  # Also stop input stream

        # Stop context manager
        get_context_manager().stop(timeout=timeout)

        # Join input thread
        if self._input_thread is not None:
            try:
                self._input_thread.join(timeout=timeout)
            except Exception as e:
                log(f"Error joining input thread: {e}", level="DEBUG")
            self._input_thread = None

        # Join other threads
        for t in self.threads:
            try:
                t.join(timeout=timeout)
            except Exception as e:
                log(f"Error joining thread {t.name}: {e}", level="DEBUG")

        self.strategy = None
        self._current_device = None
        self._running = False

    def change_input_device(self, new_device: int, timeout: float = 1.0) -> bool:
        """
        Hot-swap the input device without stopping the rest of the pipeline.

        Args:
            new_device: New device index to switch to.
            timeout: Max time to wait for old stream to close.

        Returns:
            True if switch succeeded, False otherwise.
        """
        if not self._running:
            log("Cannot change device: not running", level="WARNING")
            return False

        if new_device == self._current_device:
            log(f"Device {new_device} already active, no change needed", level="DEBUG")
            return True

        log(
            f"Hot-swapping input device from {self._current_device} to {new_device}",
            level="INFO",
        )

        # Stop the current input stream thread
        self._input_stop_event.set()
        if self._input_thread is not None:
            try:
                self._input_thread.join(timeout=timeout)
            except Exception as e:
                log(f"Error joining old input thread: {e}", level="DEBUG")

        # Reset and start new input stream
        self._input_stop_event = threading.Event()
        self._current_device = new_device
        self._input_thread = threading.Thread(
            target=self._input_stream_thread,
            args=(new_device,),
            daemon=True,
            name="input-stream",
        )
        self._input_thread.start()

        log(f"Input device switched to {new_device}", level="INFO")
        return True
