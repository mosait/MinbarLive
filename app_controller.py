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
)
from utils.history import log_transcription_and_translation
from utils.context_manager import get_context_manager
from audio.capture import audio_callback, get_default_input_device, is_silence
from audio.writer import segment_writer, async_write_audio
from translation.translator import translate_text


class AppController:
    def __init__(self):
        self.stop_event = threading.Event()
        self._input_stop_event = threading.Event()  # Separate stop for input stream
        self._input_thread: threading.Thread | None = None
        self._current_device: int | None = None
        self.threads: list[threading.Thread] = []
        self.translation_queue: queue.Queue[str] = queue.Queue()
        self._running = False

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
                    transcription_model = (
                        settings.transcription_model or DEFAULT_TRANSCRIPTION_MODEL
                    )

                    with open(file_path, "rb") as audio_file:
                        # Pass language hint if configured, otherwise auto-detect
                        transcribe_kwargs = {
                            "model": transcription_model,
                            "file": audio_file,
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
                            max_retries=3,
                            operation_name="Transcription",
                        )

                    log(f"AUDIO-PROCESSOR Transcription received", level="DEBUG")

                    # Check if same language (skip summarization if so)
                    same_language = settings.source_language == settings.target_language

                    # Add to context manager (skip summarization for same-language mode)
                    context_mgr.add_transcription(
                        transcription, enable_summarization=not same_language
                    )
                    context = "" if same_language else context_mgr.get_context()

                    if same_language:
                        log(f"AUDIO-PROCESSOR Same-language mode: {file}", level="INFO")
                    else:
                        log(
                            f"AUDIO-PROCESSOR Translation started: {file}", level="INFO"
                        )
                    translation = translate_text(transcription, context)

                    self.translation_queue.put(translation)

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
                    log_transcription_and_translation(
                        transcription, translation, duration=duration
                    )

                except Exception as e:
                    log(f"AUDIO-PROCESSOR Error for {file}: {e}", level="ERROR")

            time.sleep(0.2)

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
        except Exception as e:
            log(f"InputStream error: {e}", level="ERROR")

    def start(self, input_device: int | None = None):
        if self._running:
            return

        self.stop_event = threading.Event()
        self._input_stop_event = threading.Event()
        self.threads = []

        if input_device is None:
            input_device = get_default_input_device()

        self._current_device = input_device
        log(f"Using input device index: {input_device}", level="INFO")

        # Log the models being used
        settings = load_settings()
        log(f"Translation model: {settings.translation_model}", level="INFO")
        log(f"Transcription model: {settings.transcription_model}", level="INFO")

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
