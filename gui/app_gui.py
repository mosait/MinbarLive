"""Main application GUI with subtitle display, start/stop, key management, and live logs."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk, PhotoImage

import os
import sys
import sounddevice as sd
from screeninfo import get_monitors

from config import ICON_PATH, ICON_PATH_PNG
from gui.subtitle_window import SubtitleWindow
from utils.logging import log, log_queue
from version import __version__
from utils.settings import (
    load_settings,
    save_settings,
    TARGET_LANGUAGE_NAMES,
    SOURCE_LANGUAGES,
    SUBTITLE_MODES,
    SUBTITLE_MODE_STATIC,
    SUBTITLE_MODE_STACK,
    SUBTITLE_MODE_CONTINUOUS,
    TRANSLATION_MODELS,
    DEFAULT_TRANSLATION_MODEL,
    TRANSCRIPTION_MODELS,
    DEFAULT_TRANSCRIPTION_MODEL,
)
from utils.openai_client import has_api_key
from utils.api_key_manager import (
    ensure_api_key_on_startup,
    prompt_for_api_key,
    remove_api_key,
)


class AppGUI(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # --- Cross-platform styling ---
        # Configure ttk styles for cross-platform button appearance
        style = ttk.Style()

        # Use 'clam' theme for consistent cross-platform coloring (works on all OS)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # Start button - green
        style.configure(
            "Start.TButton",
            font=("Helvetica", 10, "bold"),
            background="#28a745",
            foreground="white",
        )
        style.map(
            "Start.TButton",
            background=[("active", "#1e7e34"), ("disabled", "#3a3a3a")],
            foreground=[("disabled", "#888888")],
        )

        # Stop button - red when enabled, gray when disabled
        style.configure(
            "Stop.TButton",
            font=("Helvetica", 10, "bold"),
            background="#dc3545",
            foreground="white",
        )
        style.map(
            "Stop.TButton",
            background=[("active", "#c82333"), ("disabled", "#3a3a3a")],
            foreground=[("disabled", "#888888")],
        )

        # Running button style (disabled grey indicator)
        style.configure(
            "Running.TButton",
            font=("Helvetica", 10, "bold"),
            background="#3a3a3a",
            foreground="#888888",
        )
        style.map(
            "Running.TButton",
            background=[("disabled", "#3a3a3a")],
            foreground=[("disabled", "#888888")],
        )

        # Action buttons - white background
        style.configure(
            "Action.TButton",
            font=("Helvetica", 10),
            background="white",
            foreground="black",
        )
        style.map(
            "Action.TButton",
            background=[("active", "#e0e0e0")],
        )

        # Default TButton - white background
        style.configure(
            "TButton",
            background="white",
            foreground="black",
        )
        style.map(
            "TButton",
            background=[("active", "#e0e0e0")],
        )

        # Combobox styling - white background
        style.configure(
            "TCombobox",
            fieldbackground="white",
            background="white",
            foreground="black",
            arrowcolor="black",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "white"), ("disabled", "#4a4a4a")],
            foreground=[("readonly", "black"), ("disabled", "#888888")],
            background=[("readonly", "white"), ("disabled", "#4a4a4a")],
        )

        # Disabled combobox style - grey background
        style.configure(
            "Disabled.TCombobox",
            fieldbackground="#4a4a4a",
            background="#4a4a4a",
            foreground="#888888",
        )
        style.map(
            "Disabled.TCombobox",
            fieldbackground=[("readonly", "#4a4a4a"), ("disabled", "#4a4a4a")],
            foreground=[("readonly", "#888888"), ("disabled", "#888888")],
        )

        # --- Advanced Settings styles (dark themed for Mac compatibility) ---
        # Dark toggle button for advanced settings header
        style.configure(
            "AdvancedToggle.TButton",
            font=("Helvetica", 9),
            background="#222222",
            foreground="white",
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "AdvancedToggle.TButton",
            background=[("active", "#333333")],
            foreground=[("active", "white")],
            relief=[("pressed", "flat"), ("active", "flat")],
        )

        # Dark frame for advanced settings content
        style.configure(
            "AdvancedFrame.TFrame",
            background="#1a1a1a",
        )

        # Dark label for advanced settings
        style.configure(
            "AdvancedLabel.TLabel",
            background="#1a1a1a",
            foreground="white",
        )

        # Gray hint label for advanced settings
        style.configure(
            "AdvancedHint.TLabel",
            background="#1a1a1a",
            foreground="gray",
            font=("Helvetica", 9),
        )

        # Dark checkbutton for advanced settings
        style.configure(
            "AdvancedCheck.TCheckbutton",
            background="#1a1a1a",
            foreground="white",
        )
        style.map(
            "AdvancedCheck.TCheckbutton",
            background=[("active", "#1a1a1a")],
            foreground=[("active", "white")],
        )
        # ----------------------------------------

        self._running = False
        self._log_polling = False
        self._height_slider_after_id = None  # For debouncing height slider

        # Control window (not fullscreen)
        self.title(f"MinbarLive v{__version__}")

        # Set window / taskbar icon EARLY (before geometry/attributes)
        # This ensures the icon appears correctly in taskbar and title bar
        if sys.platform.startswith("win"):
            if os.path.exists(ICON_PATH):
                self.iconbitmap(default=ICON_PATH)
                self.iconbitmap(ICON_PATH)  # Windows (.ico)
        else:
            if os.path.exists(ICON_PATH_PNG):
                try:
                    icon = PhotoImage(file=ICON_PATH_PNG)
                    # Resize if too large to prevent X11 BadLength && Xlib length error
                    w, h = icon.width(), icon.height()
                    if w > 256 or h > 256:
                        factor = max(w // 256, h // 256) + 1
                        icon = icon.subsample(factor, factor)
                    self.iconphoto(True, icon)  # macOS / Linux (.png)
                except Exception as e:
                    print(f"Failed to load icon: {e}")

        self.configure(bg="black")
        self.geometry("950x750")

        # Keep control panel always on top so it's accessible even with large subtitle windows
        self.attributes("-topmost", True)

        self.bind("<Escape>", lambda e: self.on_close())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Top control bar ---
        top = tk.Frame(self, bg="black")
        top.pack(side="top", fill="x")

        self.start_btn = ttk.Button(
            top,
            text="▶ Start",
            command=self.on_start,
            width=12,
            style="Start.TButton",
        )
        self.start_btn.pack(side="left", padx=8, pady=6)

        self.stop_btn = ttk.Button(
            top,
            text="■ Stop",
            command=self.on_stop,
            width=12,
            state="disabled",
            style="Stop.TButton",
        )
        self.stop_btn.pack(side="left", padx=8, pady=6)

        self.change_key_btn = ttk.Button(
            top,
            text="Change Key",
            command=self.on_change_key,
            width=14,
            style="Action.TButton",
        )
        self.change_key_btn.pack(side="left", padx=8, pady=6)

        self.remove_key_btn = ttk.Button(
            top,
            text="Remove Key",
            command=self.on_remove_key,
            width=14,
            style="Action.TButton",
        )
        self.remove_key_btn.pack(side="left", padx=8, pady=6)

        # Font size controls
        tk.Label(top, text="  Font:", fg="white", bg="black").pack(
            side="left", padx=(8, 2)
        )
        self.font_increase_btn = ttk.Button(
            top, text="+", command=self._increase_subtitle_font, width=3
        )
        self.font_increase_btn.pack(side="left", padx=2, pady=6)
        self.font_decrease_btn = ttk.Button(
            top, text="−", command=self._decrease_subtitle_font, width=3
        )
        self.font_decrease_btn.pack(side="left", padx=2, pady=6)

        # Window height slider (5% to 100% of screen)
        tk.Label(top, text="  Height:", fg="white", bg="black").pack(
            side="left", padx=(8, 2)
        )
        self.height_slider = tk.Scale(
            top,
            from_=5,
            to=100,
            orient="horizontal",
            length=100,
            showvalue=True,
            bg="black",
            fg="white",
            troughcolor="#333333",
            highlightthickness=0,
            command=self._on_height_slider_change,
        )
        self.height_slider.pack(side="left", padx=2, pady=2)
        tk.Label(top, text="%", fg="white", bg="black").pack(side="left")

        self.status_label = tk.Label(top, text="Stopped", fg="white", bg="black")
        self.status_label.pack(side="right", padx=10)

        # --- Settings bar (screen + input device selection) ---
        settings_frame = tk.Frame(self, bg="black")
        settings_frame.pack(side="top", fill="x", pady=(8, 0))

        # Screen selection
        tk.Label(settings_frame, text="Subtitle Screen:", fg="white", bg="black").pack(
            side="left", padx=(8, 4)
        )
        self._monitors = get_monitors()
        self._monitor_names = [
            f"{i}: {m.name} ({m.width}x{m.height})"
            for i, m in enumerate(self._monitors)
        ]
        self.screen_var = tk.StringVar()
        self.screen_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.screen_var,
            values=self._monitor_names,
            state="readonly",
            width=30,
        )
        self.screen_combo.pack(side="left", padx=4)

        # Load saved settings
        self._saved_settings = load_settings()

        # Default to saved monitor or second monitor if available
        saved_monitor = self._saved_settings.monitor_index
        if saved_monitor < len(self._monitors):
            default_screen_idx = saved_monitor
        else:
            default_screen_idx = 1 if len(self._monitors) > 1 else 0
        self.screen_combo.current(default_screen_idx)
        self.screen_combo.bind("<<ComboboxSelected>>", self._on_screen_change)

        # Spacing
        tk.Label(settings_frame, text="   ", bg="black").pack(side="left")

        # Input device selection
        tk.Label(settings_frame, text="Input Device:", fg="white", bg="black").pack(
            side="left", padx=(8, 4)
        )
        self._input_devices = self._get_input_devices()
        self._device_names = [f"{idx}: {name}" for idx, name in self._input_devices]
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.device_var,
            values=self._device_names,
            state="readonly",
            width=40,
        )
        self.device_combo.pack(side="left", padx=4)

        # Try to restore saved device by name, or default to index 1
        default_device_idx = 1 if len(self._input_devices) > 1 else 0
        saved_device_name = self._saved_settings.input_device_name
        if saved_device_name:
            for i, (idx, name) in enumerate(self._input_devices):
                if name == saved_device_name:
                    default_device_idx = i
                    break
        self.device_combo.current(default_device_idx)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_change)

        # --- Second settings row (language selection) ---
        settings_frame2 = tk.Frame(self, bg="black")
        settings_frame2.pack(side="top", fill="x", pady=(4, 0))

        # Source language selection (spoken language)
        tk.Label(settings_frame2, text="Source:", fg="white", bg="black").pack(
            side="left", padx=(8, 4)
        )
        self._source_lang_names = [name for name, code in SOURCE_LANGUAGES]
        self.source_lang_var = tk.StringVar()
        self.source_lang_combo = ttk.Combobox(
            settings_frame2,
            textvariable=self.source_lang_var,
            values=self._source_lang_names,
            state="readonly",
            width=15,
        )
        self.source_lang_combo.pack(side="left", padx=4)

        # Restore saved source language or default to Arabic
        saved_source = self._saved_settings.source_language
        if saved_source in self._source_lang_names:
            self.source_lang_combo.current(self._source_lang_names.index(saved_source))
        else:
            self.source_lang_combo.current(0)  # Default to Arabic
        self.source_lang_combo.bind(
            "<<ComboboxSelected>>", self._on_source_language_change
        )

        # Arrow label
        tk.Label(
            settings_frame2, text=" → ", fg="white", bg="black", font=("Helvetica", 12)
        ).pack(side="left", padx=(4, 4))

        # Target language selection
        tk.Label(settings_frame2, text="Target:", fg="white", bg="black").pack(
            side="left", padx=(4, 4)
        )
        self.language_var = tk.StringVar()
        self.language_combo = ttk.Combobox(
            settings_frame2,
            textvariable=self.language_var,
            values=TARGET_LANGUAGE_NAMES,
            state="readonly",
            width=15,
        )
        self.language_combo.pack(side="left", padx=4)

        # Restore saved language or default to German
        saved_language = self._saved_settings.target_language
        if saved_language in TARGET_LANGUAGE_NAMES:
            self.language_combo.current(TARGET_LANGUAGE_NAMES.index(saved_language))
        else:
            self.language_combo.current(0)  # Default to first (German)
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        tk.Label(
            settings_frame2,
            text="(Quran/Athan always Arabic)",
            fg="gray",
            bg="black",
            font=("Helvetica", 9),
        ).pack(side="left", padx=(12, 4))

        # Subtitle mode dropdown
        tk.Label(settings_frame2, text="  Subtitles:", fg="white", bg="black").pack(
            side="left", padx=(12, 4)
        )
        # User-friendly labels for modes (order: continuous, stack, static)
        self._subtitle_mode_labels = {
            SUBTITLE_MODE_CONTINUOUS: "Continuous (ticker)",
            SUBTITLE_MODE_STACK: "Stack (scroll up)",
            SUBTITLE_MODE_STATIC: "Static (latest only)",
        }
        # Use SUBTITLE_MODES to ensure correct order
        self._subtitle_mode_values = [
            m for m in SUBTITLE_MODES if m in self._subtitle_mode_labels
        ]
        self._subtitle_mode_display = [
            self._subtitle_mode_labels[m] for m in self._subtitle_mode_values
        ]

        self.subtitle_mode_var = tk.StringVar()
        self.subtitle_mode_combo = ttk.Combobox(
            settings_frame2,
            textvariable=self.subtitle_mode_var,
            values=self._subtitle_mode_display,
            state="readonly",
            width=18,
        )
        self.subtitle_mode_combo.pack(side="left", padx=4)

        # Restore saved mode
        saved_mode = self._saved_settings.subtitle_mode
        if saved_mode in self._subtitle_mode_values:
            self.subtitle_mode_combo.current(
                self._subtitle_mode_values.index(saved_mode)
            )
        else:
            self.subtitle_mode_combo.current(0)  # Default to continuous
        self.subtitle_mode_combo.bind(
            "<<ComboboxSelected>>", self._on_subtitle_mode_change
        )

        # Scroll speed controls (for continuous mode) - next to mode dropdown
        self.speed_label = tk.Label(
            settings_frame2, text="  Speed:", fg="white", bg="black"
        )
        self.speed_label.pack(side="left", padx=(4, 2))
        self.speed_decrease_btn = ttk.Button(
            settings_frame2, text="−", command=self._decrease_scroll_speed, width=3
        )
        self.speed_decrease_btn.pack(side="left", padx=1, pady=2)
        self.speed_increase_btn = ttk.Button(
            settings_frame2, text="+", command=self._increase_scroll_speed, width=3
        )
        self.speed_increase_btn.pack(side="left", padx=1, pady=2)

        # Transparent checkbox (for static mode only)
        self.transparent_var = tk.BooleanVar(
            value=self._saved_settings.transparent_static
        )
        self.transparent_checkbox = tk.Checkbutton(
            settings_frame2,
            text="Transparent",
            variable=self.transparent_var,
            command=self._on_transparent_change,
            fg="white",
            bg="black",
            selectcolor="black",
            activebackground="black",
            activeforeground="white",
        )
        # Don't pack yet - will be shown/hidden based on mode

        # --- Advanced Settings (collapsible) ---
        self._advanced_expanded = False

        # Header bar with toggle button
        advanced_header = tk.Frame(self, bg="black")
        advanced_header.pack(side="top", fill="x", pady=(8, 0))

        self.advanced_toggle_btn = ttk.Button(
            advanced_header,
            text="▶ Advanced Settings",
            command=self._toggle_advanced_settings,
            style="AdvancedToggle.TButton",
            cursor="hand2",
        )
        self.advanced_toggle_btn.pack(side="left", padx=8)

        # Advanced settings content frame (hidden by default)
        self.advanced_frame = ttk.Frame(self, style="AdvancedFrame.TFrame")
        # Don't pack yet - will be shown when expanded

        # Model selection inside advanced frame using grid for alignment
        model_grid = ttk.Frame(self.advanced_frame, style="AdvancedFrame.TFrame")
        model_grid.pack(side="top", fill="x", pady=8, padx=8)

        # Configure grid columns
        model_grid.columnconfigure(0, weight=0)  # Labels column
        model_grid.columnconfigure(1, weight=0)  # Checkbox column
        model_grid.columnconfigure(2, weight=0)  # Combobox column
        model_grid.columnconfigure(3, weight=1)  # Hint text column

        # Translation Model row
        ttk.Label(
            model_grid, text="Translation Model:", style="AdvancedLabel.TLabel"
        ).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)

        # Use Default checkbox for translation model
        self.use_default_translation_var = tk.BooleanVar(
            value=self._saved_settings.use_default_translation_model
        )
        self.use_default_translation_cb = ttk.Checkbutton(
            model_grid,
            text="Use Default",
            variable=self.use_default_translation_var,
            command=self._on_use_default_translation_change,
            style="AdvancedCheck.TCheckbutton",
        )
        self.use_default_translation_cb.grid(
            row=0, column=1, sticky="w", padx=4, pady=4
        )

        self._model_display_names = [name for name, _ in TRANSLATION_MODELS]
        self._model_ids = [model_id for _, model_id in TRANSLATION_MODELS]
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            model_grid,
            textvariable=self.model_var,
            values=self._model_display_names,
            state=(
                "disabled"
                if self._saved_settings.use_default_translation_model
                else "readonly"
            ),
            width=28,
        )
        self.model_combo.grid(row=0, column=2, sticky="w", padx=4, pady=4)

        # Restore saved model or default
        saved_model = self._saved_settings.translation_model
        if saved_model in self._model_ids:
            self.model_combo.current(self._model_ids.index(saved_model))
        else:
            # Default to gpt-4o-mini
            default_idx = (
                self._model_ids.index(DEFAULT_TRANSLATION_MODEL)
                if DEFAULT_TRANSLATION_MODEL in self._model_ids
                else 0
            )
            self.model_combo.current(default_idx)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        # Hint text
        ttk.Label(
            model_grid,
            text="(Affects cost and quality)",
            style="AdvancedHint.TLabel",
        ).grid(row=0, column=3, sticky="w", padx=(8, 0), pady=4)

        # Transcription Model row
        ttk.Label(
            model_grid, text="Transcription Model:", style="AdvancedLabel.TLabel"
        ).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)

        # Use Default checkbox for transcription model
        self.use_default_transcription_var = tk.BooleanVar(
            value=self._saved_settings.use_default_transcription_model
        )
        self.use_default_transcription_cb = ttk.Checkbutton(
            model_grid,
            text="Use Default",
            variable=self.use_default_transcription_var,
            command=self._on_use_default_transcription_change,
            style="AdvancedCheck.TCheckbutton",
        )
        self.use_default_transcription_cb.grid(
            row=1, column=1, sticky="w", padx=4, pady=4
        )

        self._transcription_display_names = [name for name, _ in TRANSCRIPTION_MODELS]
        self._transcription_ids = [model_id for _, model_id in TRANSCRIPTION_MODELS]
        self.transcription_var = tk.StringVar()
        self.transcription_combo = ttk.Combobox(
            model_grid,
            textvariable=self.transcription_var,
            values=self._transcription_display_names,
            state=(
                "disabled"
                if self._saved_settings.use_default_transcription_model
                else "readonly"
            ),
            width=28,
        )
        self.transcription_combo.grid(row=1, column=2, sticky="w", padx=4, pady=4)

        # Restore saved transcription model or default
        saved_transcription = self._saved_settings.transcription_model
        if saved_transcription in self._transcription_ids:
            self.transcription_combo.current(
                self._transcription_ids.index(saved_transcription)
            )
        else:
            default_idx = (
                self._transcription_ids.index(DEFAULT_TRANSCRIPTION_MODEL)
                if DEFAULT_TRANSCRIPTION_MODEL in self._transcription_ids
                else 0
            )
            self.transcription_combo.current(default_idx)
        self.transcription_combo.bind(
            "<<ComboboxSelected>>", self._on_transcription_model_change
        )

        ttk.Label(
            model_grid,
            text="(Speech to text)",
            style="AdvancedHint.TLabel",
        ).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=4)

        # Processing Strategy row
        ttk.Label(
            model_grid, text="Processing Strategy:", style="AdvancedLabel.TLabel"
        ).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)

        # Use Default checkbox for processing strategy
        self.use_default_strategy_var = tk.BooleanVar(
            value=self._saved_settings.use_default_processing_strategy
        )
        self.use_default_strategy_cb = ttk.Checkbutton(
            model_grid,
            text="Use Default",
            variable=self.use_default_strategy_var,
            command=self._on_use_default_strategy_change,
            style="AdvancedCheck.TCheckbutton",
        )
        self.use_default_strategy_cb.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        self._strategy_display_names = ["Chunk-based", "Semantic buffering"]
        self._strategy_ids = ["chunk", "semantic"]
        self.strategy_var = tk.StringVar()
        self.strategy_combo = ttk.Combobox(
            model_grid,
            textvariable=self.strategy_var,
            values=self._strategy_display_names,
            state=(
                "disabled"
                if self._saved_settings.use_default_processing_strategy
                else "readonly"
            ),
            width=28,
        )
        self.strategy_combo.grid(row=2, column=2, sticky="w", padx=4, pady=4)

        # Restore saved strategy or default
        saved_strategy = self._saved_settings.processing_strategy
        if saved_strategy in self._strategy_ids:
            self.strategy_combo.current(self._strategy_ids.index(saved_strategy))
        else:
            self.strategy_combo.current(1)  # Default to semantic
        self.strategy_combo.bind("<<ComboboxSelected>>", self._on_strategy_change)

        # Hint label (changes based on running state)
        self.strategy_hint_label = ttk.Label(
            model_grid,
            text="(Semantic waits for sentences)",
            style="AdvancedHint.TLabel",
        )
        self.strategy_hint_label.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=4)

        # --- Log area only (controls window) ---
        self.log_frame = tk.Frame(self, bg="black")
        self.log_frame.pack(side="top", fill="both", expand=True)

        tk.Label(self.log_frame, text="Logs", fg="white", bg="black").pack(
            anchor="w", padx=8, pady=(8, 0)
        )

        self.log_text = tk.Text(
            self.log_frame, height=30, width=60, bg="#111111", fg="white", wrap="word"
        )
        self.log_text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self.log_text.configure(state="disabled")

        scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y", pady=8, padx=(0, 8))
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Separate subtitle window (use selected monitor and saved font size)
        log(
            f"Creating SubtitleWindow with font_size_base={self._saved_settings.font_size_base}, subtitle_mode={self._saved_settings.subtitle_mode}",
            level="INFO",
        )
        self.subtitle_window = SubtitleWindow(
            self,
            on_close=self.on_close,
            monitor_index=default_screen_idx,
            font_size_base=self._saved_settings.font_size_base,
            target_language=self._saved_settings.target_language,
            subtitle_mode=self._saved_settings.subtitle_mode,
            scroll_speed=self._saved_settings.scroll_speed,
            transparent_static=self._saved_settings.transparent_static,
            window_height_percent=self._saved_settings.window_height_percent,
        )

        # Set height slider to saved value
        self.height_slider.set(self._saved_settings.window_height_percent)

        # Ensure key is set on first run
        self._ensure_api_key_on_startup()

        # Initialize speed button states based on current mode
        self._update_speed_button_states()

        # Start by default (after UI is ready). If the key prompt was cancelled,
        # the app will be closing and this won't matter.
        if has_api_key():
            self.after(150, self.on_start)

        # Poll for translations always (they only arrive when running)
        self.after(100, self._process_translation_queue)

    def _ensure_api_key_on_startup(self):
        ensure_api_key_on_startup(
            root=self,
            on_close=self.on_close,
            on_change_key=self.on_change_key,
        )

    def _append_log_line(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_logs(self):
        if not self._log_polling:
            return
        try:
            while not log_queue.empty():
                self._append_log_line(log_queue.get_nowait())
        except Exception as e:
            # Log polling errors are non-critical, but log them for debugging
            log(f"Log polling error: {e}", level="DEBUG")
        self.after(100, self._poll_logs)

    def _start_log_polling(self):
        if self._log_polling:
            return
        self._log_polling = True
        self._poll_logs()

    def _stop_log_polling(self):
        self._log_polling = False

    def _process_translation_queue(self):
        try:
            while not self.controller.translation_queue.empty():
                text = self.controller.translation_queue.get_nowait()
                if self.subtitle_window and self.subtitle_window.winfo_exists():
                    self.subtitle_window.add_subtitle(text)
        except Exception as e:
            log(f"Translation queue processing error: {e}", level="DEBUG")
        self.after(100, self._process_translation_queue)

    def on_change_key(self, startup: bool = False):
        prompt_for_api_key(root=self, startup=startup, on_close=self.on_close)

    def on_remove_key(self):
        remove_api_key(is_running=self._running)

    def on_start(self):
        if not has_api_key():
            self.on_change_key(startup=True)
            if not has_api_key():
                return

        try:
            device_idx = self.get_selected_device_index()
            self.controller.start(input_device=device_idx)
        except Exception as e:
            messagebox.showerror("Start failed", str(e))
            return

        self._running = True
        self.start_btn.configure(
            state="disabled", text="● Running", style="Running.TButton"
        )
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Running", fg="#28a745")
        # Disable strategy controls during running
        self.use_default_strategy_cb.configure(state="disabled")
        self.strategy_combo.configure(state="disabled")
        self.strategy_hint_label.configure(
            text="⚠ Stop program to change", foreground="#ff6b6b"
        )
        self._start_log_polling()
        log("Started.", level="INFO")

    def on_stop(self):
        try:
            self.controller.stop()
        except Exception as e:
            messagebox.showerror("Stop failed", str(e))
            return

        self._running = False
        self.start_btn.configure(state="normal", text="▶ Start", style="Start.TButton")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Stopped", fg="white")
        # Re-enable strategy controls
        self.use_default_strategy_cb.configure(state="normal")
        if not self._saved_settings.use_default_processing_strategy:
            self.strategy_combo.configure(state="readonly")
        self.strategy_hint_label.configure(
            text="(Semantic waits for sentences)", foreground="gray"
        )
        self._stop_log_polling()
        log("Stopped.", level="INFO")

    def _get_input_devices(self) -> list[tuple[int, str]]:
        """Get list of available input devices."""
        devices = sd.query_devices()
        return [
            (i, d["name"]) for i, d in enumerate(devices) if d["max_input_channels"] > 0
        ]

    def _on_device_change(self, event=None):
        """Handle input device selection change."""
        selection = self.device_combo.current()
        if 0 <= selection < len(self._input_devices):
            device_idx, device_name = self._input_devices[selection]
            # Save the device name for persistence
            self._saved_settings.input_device_name = device_name
            self._save_current_settings()
            log(f"Input device changed to: {device_name}", level="INFO")

            # Hot-swap device if currently running
            if self._running:
                self.controller.change_input_device(device_idx)

    def _on_screen_change(self, event=None):
        """Handle screen selection change."""
        selection = self.screen_combo.current()
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.set_monitor(selection)
        # Save setting
        self._saved_settings.monitor_index = selection
        self._save_current_settings()
        log(f"Subtitle screen changed to monitor {selection}.", level="INFO")

    def _on_language_change(self, event=None):
        """Handle target language selection change."""
        selection = self.language_combo.current()
        if 0 <= selection < len(TARGET_LANGUAGE_NAMES):
            language = TARGET_LANGUAGE_NAMES[selection]
            self._saved_settings.target_language = language
            self._save_current_settings()
            # Update subtitle window footer
            if self.subtitle_window and self.subtitle_window.winfo_exists():
                self.subtitle_window.set_language(language)
            log(f"Target language changed to: {language}", level="INFO")

    def _on_source_language_change(self, event=None):
        """Handle source language selection change."""
        selection = self.source_lang_combo.current()
        if 0 <= selection < len(self._source_lang_names):
            language = self._source_lang_names[selection]
            self._saved_settings.source_language = language
            self._save_current_settings()
            log(f"Source language changed to: {language}", level="INFO")

    def _on_subtitle_mode_change(self, event=None):
        """Handle subtitle mode dropdown change."""
        selection = self.subtitle_mode_combo.current()
        if 0 <= selection < len(self._subtitle_mode_values):
            mode = self._subtitle_mode_values[selection]
            self._saved_settings.subtitle_mode = mode
            self._save_current_settings()
            if self.subtitle_window and self.subtitle_window.winfo_exists():
                self.subtitle_window.set_subtitle_mode(mode)
            # Update speed button states based on new mode
            self._update_speed_button_states()
            log(f"Subtitle mode changed to: {mode}", level="INFO")

    def get_selected_device_index(self) -> int:
        """Get the selected input device index."""
        selection = self.device_combo.current()
        if 0 <= selection < len(self._input_devices):
            return self._input_devices[selection][0]
        return 1  # Default fallback

    def _increase_subtitle_font(self):
        """Increase subtitle font size."""
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.increase_font()
            self._saved_settings.font_size_base = (
                self.subtitle_window.get_font_size_base()
            )
            self._save_current_settings()

    def _decrease_subtitle_font(self):
        """Decrease subtitle font size."""
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.decrease_font()
            self._saved_settings.font_size_base = (
                self.subtitle_window.get_font_size_base()
            )
            self._save_current_settings()

    def _on_height_slider_change(self, value):
        """Handle window height slider change with debouncing."""
        percent = int(float(value))
        # Cancel any pending update
        if hasattr(self, "_height_slider_after_id") and self._height_slider_after_id:
            self.after_cancel(self._height_slider_after_id)
        # Schedule the actual update after a short delay (debounce)
        self._height_slider_after_id = self.after(
            50, lambda: self._apply_height_change(percent)
        )

    def _apply_height_change(self, percent: int):
        """Apply the height change after debounce delay."""
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.set_window_height_percent(percent)
            self._saved_settings.window_height_percent = percent
            self._save_current_settings()

    def _increase_scroll_speed(self):
        """Increase continuous scroll speed."""
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            speed = self.subtitle_window.increase_scroll_speed()
            self._update_speed_button_states(speed)
            self._saved_settings.scroll_speed = speed
            self._save_current_settings()
            log(f"Scroll speed increased to: {speed}", level="INFO")

    def _decrease_scroll_speed(self):
        """Decrease continuous scroll speed."""
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            speed = self.subtitle_window.decrease_scroll_speed()
            self._update_speed_button_states(speed)
            self._saved_settings.scroll_speed = speed
            self._save_current_settings()
            log(f"Scroll speed decreased to: {speed}", level="INFO")

    def _on_transparent_change(self):
        """Handle transparent checkbox change."""
        enabled = self.transparent_var.get()
        self._saved_settings.transparent_static = enabled
        self._save_current_settings()
        if self.subtitle_window and self.subtitle_window.winfo_exists():
            self.subtitle_window.set_transparent_static(enabled)
        log(f"Transparent mode: {'enabled' if enabled else 'disabled'}", level="INFO")

    def _toggle_advanced_settings(self):
        """Toggle the advanced settings panel visibility."""
        self._advanced_expanded = not self._advanced_expanded
        if self._advanced_expanded:
            self.advanced_toggle_btn.configure(text="▼ Advanced Settings")
            self.advanced_frame.pack(side="top", fill="x", before=self.log_frame)
        else:
            self.advanced_toggle_btn.configure(text="▶ Advanced Settings")
            self.advanced_frame.pack_forget()

    def _on_model_change(self, event=None):
        """Handle translation model change."""
        idx = self.model_combo.current()
        if 0 <= idx < len(self._model_ids):
            model_id = self._model_ids[idx]
            self._saved_settings.translation_model = model_id
            self._save_current_settings()
            log(f"Translation model changed to: {model_id}", level="INFO")

    def _on_transcription_model_change(self, event=None):
        """Handle transcription model change."""
        idx = self.transcription_combo.current()
        if 0 <= idx < len(self._transcription_ids):
            model_id = self._transcription_ids[idx]
            self._saved_settings.transcription_model = model_id
            self._save_current_settings()
            log(f"Transcription model changed to: {model_id}", level="INFO")

    def _on_use_default_translation_change(self):
        """Handle Use Default checkbox change for translation model."""
        use_default = self.use_default_translation_var.get()
        self._saved_settings.use_default_translation_model = use_default
        if use_default:
            # Set to default model and disable dropdown
            default_idx = (
                self._model_ids.index(DEFAULT_TRANSLATION_MODEL)
                if DEFAULT_TRANSLATION_MODEL in self._model_ids
                else 0
            )
            self.model_combo.current(default_idx)
            self._saved_settings.translation_model = DEFAULT_TRANSLATION_MODEL
            self.model_combo.configure(state="disabled")
        else:
            self.model_combo.configure(state="readonly")
        self._save_current_settings()
        if use_default:
            log(
                f"Use default translation model: {DEFAULT_TRANSLATION_MODEL}",
                level="INFO",
            )
        else:
            log("Use default translation model: disabled", level="INFO")

    def _on_use_default_transcription_change(self):
        """Handle Use Default checkbox change for transcription model."""
        use_default = self.use_default_transcription_var.get()
        self._saved_settings.use_default_transcription_model = use_default
        if use_default:
            # Set to default model and disable dropdown
            default_idx = (
                self._transcription_ids.index(DEFAULT_TRANSCRIPTION_MODEL)
                if DEFAULT_TRANSCRIPTION_MODEL in self._transcription_ids
                else 0
            )
            self.transcription_combo.current(default_idx)
            self._saved_settings.transcription_model = DEFAULT_TRANSCRIPTION_MODEL
            self.transcription_combo.configure(state="disabled")
        else:
            self.transcription_combo.configure(state="readonly")
        self._save_current_settings()
        if use_default:
            log(
                f"Use default transcription model: {DEFAULT_TRANSCRIPTION_MODEL}",
                level="INFO",
            )
        else:
            log("Use default transcription model: disabled", level="INFO")

    def _update_speed_button_states(self, speed: float = None):
        """Update speed/transparent controls visibility based on mode."""
        is_continuous = self._saved_settings.subtitle_mode == SUBTITLE_MODE_CONTINUOUS
        is_static = self._saved_settings.subtitle_mode == SUBTITLE_MODE_STATIC

        if is_static:
            # Hide speed controls, show transparent checkbox
            self.speed_label.pack_forget()
            self.speed_decrease_btn.pack_forget()
            self.speed_increase_btn.pack_forget()
            self.transparent_checkbox.pack(side="left", padx=(8, 2))
        elif is_continuous:
            # Show speed controls, hide transparent checkbox
            self.transparent_checkbox.pack_forget()
            self.speed_label.pack(side="left", padx=(4, 2))
            self.speed_decrease_btn.pack(side="left", padx=1, pady=2)
            self.speed_increase_btn.pack(side="left", padx=1, pady=2)
        else:
            # Stack mode: hide both speed controls and transparent checkbox
            self.transparent_checkbox.pack_forget()
            self.speed_label.pack_forget()
            self.speed_decrease_btn.pack_forget()
            self.speed_increase_btn.pack_forget()

    def _on_strategy_change(self, event=None):
        """Handle processing strategy dropdown change."""
        selection = self.strategy_combo.current()
        strategy = self._strategy_ids[selection]
        self._saved_settings.processing_strategy = strategy
        self._save_current_settings()
        log(f"Processing strategy changed to: {strategy}", level="INFO")

    def _on_use_default_strategy_change(self):
        """Handle use default processing strategy checkbox change."""
        use_default = self.use_default_strategy_var.get()
        self._saved_settings.use_default_processing_strategy = use_default
        if use_default:
            # Reset to default (semantic)
            self.strategy_combo.current(1)  # semantic
            self._saved_settings.processing_strategy = "semantic"
            self.strategy_combo.configure(state="disabled")
        else:
            self.strategy_combo.configure(state="readonly")
        self._save_current_settings()
        if use_default:
            log("Use default processing strategy: semantic", level="INFO")
        else:
            log("Use default processing strategy: disabled", level="INFO")

    def _save_current_settings(self):
        """Save current settings to disk."""
        try:
            save_settings(self._saved_settings)
        except Exception as e:
            log(f"Failed to save settings: {e}", level="ERROR")

    def on_close(self):
        # Stop log polling
        self._stop_log_polling()

        # Ensure stopped
        try:
            self.controller.stop()
        except Exception:
            pass

        try:
            if self.subtitle_window and self.subtitle_window.winfo_exists():
                self.subtitle_window.destroy()
        except Exception:
            pass
        self.destroy()
