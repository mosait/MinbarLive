"""Dedicated subtitle window (full-screen) for displaying translations."""

from __future__ import annotations

import sys
import tkinter as tk
from screeninfo import get_monitors

from config import MAX_SUBTITLES, LINE_SPACING, MARGIN_BOTTOM, FOOTER_TRANSLATIONS_PATH
from utils.json_helpers import load_json
from utils.settings import (
    SUBTITLE_MODE_STATIC,
    SUBTITLE_MODE_STACK,
    SUBTITLE_MODE_CONTINUOUS,
)


# Load footer translations from JSON file
FOOTER_TRANSLATIONS = load_json(FOOTER_TRANSLATIONS_PATH)

# Default footer for languages not in the list
DEFAULT_FOOTER = (
    "AI Translation! Our association assumes no liability for accuracy or completeness."
)

# Continuous scroll settings
SCROLL_INTERVAL_MS = 30  # Milliseconds between scroll updates (~33 fps)


class SubtitleWindow(tk.Toplevel):
    """Full-screen window that renders subtitles in various modes."""

    def __init__(
        self,
        master: tk.Tk,
        on_close,
        monitor_index: int = 1,
        font_size_base: int = 40,
        target_language: str = "German",
        subtitle_mode: str = SUBTITLE_MODE_STATIC,
        scroll_speed: float = 1.0,
        transparent_static: bool = False,
        window_height_percent: int = 100,
        show_footer: bool = True,
    ):
        super().__init__(master)
        self._on_close = on_close
        self._monitor_index = monitor_index
        self._target_language = target_language
        self._subtitle_mode = subtitle_mode  # static, stack, or continuous
        self._scroll_animation_id = None  # For cancelling continuous scroll animation
        self._scroll_speed = scroll_speed  # Current scroll speed (pixels per frame)
        self._transparent_static = (
            transparent_static  # Transparent background for static mode
        )
        self._window_height_percent = max(5, min(100, window_height_percent))
        self._show_footer = show_footer  # Show/hide footer disclaimer

        self.configure(bg="black")

        # Configure window to be borderless but still visible to OBS/screen capture
        # We avoid overrideredirect(True) because it makes the window invisible to
        # OBS window capture on most platforms.
        self._setup_borderless_window()

        self.bind("<Escape>", lambda e: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Position on correct monitor BEFORE showing
        self._set_screen_position()

        # Canvas for subtitles
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.place(relx=0, rely=0.0, relwidth=1, relheight=1.0)

        # Font size base (divisor for calculating font size)
        self._font_size_base = font_size_base

        # Footer disclaimer (language-aware)
        footer_text = FOOTER_TRANSLATIONS.get(target_language, DEFAULT_FOOTER)
        self.footer = tk.Label(
            self,
            text=footer_text,
            font=("Helvetica", 20),
            fg="#111111",  # Dark gray instead of black (black is transparent color)
            bg="orange",
        )
        if self._show_footer:
            self.footer.place(relx=0.5, rely=1.0, anchor="s", relwidth=1.0)
        # If show_footer is False, footer is created but not placed (hidden)

        # Subtitle management
        # Each item is (text_id, text_height, line_items) where line_items may be None
        # line_items is a list of (text_id, box_id) tuples for transparent mode
        self.subtitle_stack: list[tuple] = []
        self.max_subtitles = MAX_SUBTITLES
        self.line_spacing = LINE_SPACING
        self.margin_bottom = MARGIN_BOTTOM

        self.update_idletasks()
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()
        self._update_font()

        # Apply transparent mode if needed
        if self._transparent_static and self._subtitle_mode == SUBTITLE_MODE_STATIC:
            self._apply_transparent_mode()

        # Schedule a delayed font update after window is fully rendered
        # This ensures the correct font size is applied even on first load
        self.after(100, self._delayed_font_update)

        # Start continuous scroll animation if that mode is active
        if self._subtitle_mode == SUBTITLE_MODE_CONTINUOUS:
            self.after(150, self._start_continuous_scroll)

    def _setup_borderless_window(self):
        """Configure a borderless window that remains visible to OBS/screen capture.

        Unlike overrideredirect(True), this approach keeps the window in the
        window manager's control, making it visible to OBS Window Capture.

        Platform-specific approaches:
        - Windows: Remove decorations via wm_attributes, use -toolwindow to hide from taskbar
        - macOS: Use -fullscreen or manual geometry with -toolwindow
        - Linux: Remove decorations via _MOTIF_WM_HINTS or fallback methods
        """
        # Give the window a title so OBS can identify it
        self.title("MinbarLive Subtitles")

        # Store hwnd for later use (Windows only)
        self._hwnd = None

        if sys.platform == "win32":
            # Windows: Create a borderless window visible to OBS
            # We use Windows-specific styling to remove the title bar completely
            try:
                # Get the window handle and modify window styles to remove decorations
                # This needs to happen after the window is mapped
                self.update_idletasks()

                # Use Windows API via ctypes to remove window decorations
                # while keeping the window visible to capture software
                import ctypes

                # Window style constants
                GWL_STYLE = -16
                GWL_EXSTYLE = -20
                WS_CAPTION = 0x00C00000  # Title bar
                WS_THICKFRAME = 0x00040000  # Sizing border
                WS_MINIMIZEBOX = 0x00020000
                WS_MAXIMIZEBOX = 0x00010000
                WS_SYSMENU = 0x00080000  # System menu
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_TOOLWINDOW = 0x00000080

                # Get window handle
                self._hwnd = ctypes.windll.user32.GetParent(self.winfo_id())

                # Get current style
                style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_STYLE)

                # Remove title bar and borders but keep it a normal window
                style = style & ~WS_CAPTION & ~WS_THICKFRAME
                style = style & ~WS_MINIMIZEBOX & ~WS_MAXIMIZEBOX & ~WS_SYSMENU

                # Apply new style
                ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_STYLE, style)

                # Get and modify extended style to ensure it shows in window lists
                ex_style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
                # Remove toolwindow style, add APPWINDOW to ensure it appears in capture lists
                ex_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
                ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex_style)

                # Note: We don't call SetWindowPos here - _set_screen_position will
                # handle positioning with _apply_window_position()

            except Exception:
                # Fallback: just use overrideredirect if ctypes fails
                self._hwnd = None
                self.overrideredirect(True)

        elif sys.platform == "darwin":
            # macOS: Use transparent title bar approach or fullscreen
            try:
                # Make the window borderless-looking while keeping it managed
                # On macOS, we can use the "transparent" appearance
                self.wm_attributes("-fullscreen", False)
                # Remove title bar but keep window managed
                self.tk.call(
                    "::tk::unsupported::MacWindowStyle",
                    "style",
                    self._w,
                    "plain",
                    "none",
                )
            except tk.TclError:
                # Fallback for older Tk versions
                self.overrideredirect(True)

        else:
            # Linux/Other: Use EWMH hints to remove decorations
            try:
                # Try to set _MOTIF_WM_HINTS to remove decorations
                # This keeps the window in the WM's control
                self.wm_attributes("-type", "splash")
            except tk.TclError:
                try:
                    # Alternative: try dock type
                    self.wm_attributes("-type", "dock")
                except tk.TclError:
                    # Final fallback
                    self.overrideredirect(True)

    def _delayed_font_update(self):
        """Update font after window is fully rendered."""
        self.update_idletasks()
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()
        if self.canvas_width > 0:
            self._update_font()

    def _update_font(self):
        """Recalculate font based on canvas width and font size base."""
        font_size = (
            int(self.canvas_width / self._font_size_base) if self.canvas_width else 24
        )
        font_size = max(12, min(font_size, 120))  # Clamp between 12 and 120
        self.font = ("Helvetica", font_size)

    def increase_font(self):
        """Increase subtitle font size."""
        self._font_size_base = max(20, self._font_size_base - 5)
        self._update_font()
        self._refresh_subtitles()

    def decrease_font(self):
        """Decrease subtitle font size."""
        self._font_size_base = min(80, self._font_size_base + 5)
        self._update_font()
        self._refresh_subtitles()

    def set_language(self, language: str):
        """Update the footer text based on target language."""
        self._target_language = language
        footer_text = FOOTER_TRANSLATIONS.get(language, DEFAULT_FOOTER)
        self.footer.configure(text=footer_text)

    def set_show_footer(self, enabled: bool):
        """Show or hide the footer disclaimer."""
        self._show_footer = enabled
        if enabled:
            self.footer.place(relx=0.5, rely=1.0, anchor="s", relwidth=1.0)
        else:
            self.footer.place_forget()

    def get_show_footer(self) -> bool:
        """Get current footer visibility state."""
        return self._show_footer

    def get_font_size_base(self) -> int:
        """Get current font size base value."""
        return self._font_size_base

    def increase_scroll_speed(self) -> float:
        """Increase continuous scroll speed."""
        self._scroll_speed = min(5.0, self._scroll_speed + 0.5)  # Max 5 px/frame
        return self._scroll_speed

    def decrease_scroll_speed(self) -> float:
        """Decrease continuous scroll speed."""
        self._scroll_speed = max(0.5, self._scroll_speed - 0.5)  # Min 0.5 px/frame
        return self._scroll_speed

    def get_scroll_speed(self) -> float:
        """Get current scroll speed."""
        return self._scroll_speed

    def set_transparent_static(self, enabled: bool):
        """Enable or disable transparent background for static mode."""
        self._transparent_static = enabled
        if self._subtitle_mode == SUBTITLE_MODE_STATIC:
            if enabled:
                self._apply_transparent_mode()
            else:
                self._apply_opaque_mode()
            # Refresh subtitles to apply new style
            self._refresh_subtitles()

    def get_transparent_static(self) -> bool:
        """Get current transparent static setting."""
        return self._transparent_static

    def _apply_transparent_mode(self):
        """Make the window background transparent on desktop and keyable in OBS.

        Platform-specific transparency:
        - Windows: -transparentcolor makes green invisible on desktop
        - macOS: -transparent attribute with transparent background
        - Linux: Compositor-dependent, uses alpha channel if available
        """
        # Use chroma key green for OBS compatibility
        chroma_color = "#00FF00"

        if sys.platform == "win32":
            # Windows: use transparent color (chroma green becomes invisible)
            self.configure(bg=chroma_color)
            self.canvas.configure(bg=chroma_color)
            self.wm_attributes("-transparentcolor", chroma_color)

        elif sys.platform == "darwin":
            # macOS: use native transparency
            try:
                self.wm_attributes("-transparent", True)
                # Use systemTransparent for true transparency
                self.configure(bg="systemTransparent")
                self.canvas.configure(bg="systemTransparent")
            except tk.TclError:
                # Fallback to chroma key if transparency not supported
                self.configure(bg=chroma_color)
                self.canvas.configure(bg=chroma_color)

        else:
            # Linux: Try compositor alpha transparency
            try:
                # Set background to a color we can make transparent
                self.configure(bg=chroma_color)
                self.canvas.configure(bg=chroma_color)
                # Request RGBA visual for true transparency
                # This works with compositing window managers (KDE, GNOME, etc.)
                self.wait_visibility()
                self.wm_attributes("-alpha", 0.99)  # Triggers RGBA mode
                # Now we can use transparent areas
                self.configure(bg="")
                self.canvas.configure(bg="")
            except tk.TclError:
                # Fallback to chroma key for OBS
                self.configure(bg=chroma_color)
                self.canvas.configure(bg=chroma_color)

        # Make always-on-top so subtitles stay visible over other windows
        self.wm_attributes("-topmost", True)

    def _apply_opaque_mode(self):
        """Restore normal opaque black background."""
        self.configure(bg="black")
        self.canvas.configure(bg="black")

        if sys.platform == "win32":
            self.wm_attributes("-transparentcolor", "")
        else:
            try:
                self.wm_attributes("-alpha", 1.0)
            except tk.TclError:
                pass

        # Remove always-on-top so other windows can come to front
        self.wm_attributes("-topmost", False)

    def set_subtitle_mode(self, mode: str):
        """Set subtitle display mode: static, stack, or continuous."""
        # Stop any running animation
        if self._scroll_animation_id:
            self.after_cancel(self._scroll_animation_id)
            self._scroll_animation_id = None

        old_mode = self._subtitle_mode
        self._subtitle_mode = mode
        # Clear existing subtitles when changing mode
        self._clear_all_subtitles()

        # Handle transparent mode when switching to/from static
        if mode == SUBTITLE_MODE_STATIC and self._transparent_static:
            self._apply_transparent_mode()
        elif old_mode == SUBTITLE_MODE_STATIC and self._transparent_static:
            # Switching away from static transparent mode
            self._apply_opaque_mode()

        # Start continuous scroll animation if needed
        if mode == SUBTITLE_MODE_CONTINUOUS:
            self._start_continuous_scroll()

    def get_subtitle_mode(self) -> str:
        """Get current subtitle mode."""
        return self._subtitle_mode

    def _clear_all_subtitles(self):
        """Remove all subtitle items from the canvas."""
        for item in self.subtitle_stack:
            text_id = item[0]
            line_items = item[2] if len(item) > 2 else None
            self.canvas.delete(text_id)
            if line_items:
                for line_text_id, box_id in line_items:
                    if line_text_id:
                        self.canvas.delete(line_text_id)
                    if box_id:
                        self.canvas.delete(box_id)
        self.subtitle_stack.clear()

    def _wrap_text_to_lines(self, text: str, max_width: int) -> list[str]:
        """Split text into lines that fit within max_width pixels."""
        import tkinter.font as tkfont

        font_obj = tkfont.Font(font=self.font)
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            if font_obj.measure(test_line) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text]

    def _create_outlined_text(self, x: float, y: float, text: str) -> tuple:
        """Create text with per-line dark background boxes.

        Each line gets its own box sized to fit just that line's text,
        creating a cleaner look without excess black space.
        """
        max_width = self.canvas.winfo_width() - 75
        lines = self._wrap_text_to_lines(text, max_width)

        padding_x = 20
        padding_y = 8
        line_gap = 4  # Small gap between lines

        # Calculate total height needed
        import tkinter.font as tkfont

        font_obj = tkfont.Font(font=self.font)
        line_height = font_obj.metrics("linespace")

        # We'll create lines from bottom to top since anchor is "s"
        # line_items will store (text_id, box_id) for each line
        line_items = []

        # Start from the bottom y position and work upward
        current_y = y

        for line_text in reversed(lines):
            # Create text for this line (no width constraint - single line)
            text_id = self.canvas.create_text(
                x,
                current_y,
                text=line_text,
                fill="white",
                font=self.font,
                anchor="s",
                justify="center",
            )

            # Get actual bbox of this single line
            bbox = self.canvas.bbox(text_id)
            if bbox:
                # Create box sized to this line's actual width
                box_id = self.canvas.create_rectangle(
                    bbox[0] - padding_x,
                    bbox[1] - padding_y,
                    bbox[2] + padding_x,
                    bbox[3] + padding_y,
                    fill="#1a1a1a",
                    outline="",
                )
                # Raise text above box
                self.canvas.tag_raise(text_id, box_id)
            else:
                box_id = None

            line_items.append((text_id, box_id))

            # Move up for the next line
            current_y -= line_height + line_gap

        # Reverse so line_items[0] is the top line, line_items[-1] is bottom
        line_items.reverse()

        # The "main" text_id is the bottom line (for height calculations)
        main_text_id = line_items[-1][0]

        return main_text_id, line_items

    def _refresh_subtitles(self):
        """Update font for all existing subtitles."""
        padding_x = 20
        padding_y = 8

        for item in self.subtitle_stack:
            line_items = item[2] if len(item) > 2 else None
            if line_items:
                # Update font and box for each line
                for line_text_id, box_id in line_items:
                    if line_text_id:
                        self.canvas.itemconfig(line_text_id, font=self.font)
                    if box_id:
                        bbox = self.canvas.bbox(line_text_id)
                        if bbox:
                            self.canvas.coords(
                                box_id,
                                bbox[0] - padding_x,
                                bbox[1] - padding_y,
                                bbox[2] + padding_x,
                                bbox[3] + padding_y,
                            )
            else:
                # Non-outlined text (normal mode)
                text_id = item[0]
                self.canvas.itemconfig(text_id, font=self.font)

        # Recalculate heights and reposition
        new_stack = []
        for item in self.subtitle_stack:
            text_id = item[0]
            line_items = item[2] if len(item) > 2 else None
            # Calculate total height from all lines
            if line_items and len(line_items) > 1:
                # Get bbox spanning all lines
                top_line_bbox = self.canvas.bbox(line_items[0][0])
                bottom_line_bbox = self.canvas.bbox(line_items[-1][0])
                if top_line_bbox and bottom_line_bbox:
                    text_height = bottom_line_bbox[3] - top_line_bbox[1]
                else:
                    text_height = 75
            else:
                bbox = self.canvas.bbox(text_id)
                text_height = bbox[3] - bbox[1] if bbox else 75
            new_stack.append((text_id, text_height, line_items))
        self.subtitle_stack = new_stack
        self._reposition_subtitles()

    def _set_screen_position(self, force_redraw: bool = False):
        monitors = get_monitors()
        if self._monitor_index < len(monitors):
            mon = monitors[self._monitor_index]
        elif len(monitors) > 1:
            mon = monitors[1]
        else:
            mon = monitors[0]

        if self._window_height_percent >= 100:
            # Full screen - use exact monitor dimensions
            x, y, width, height = mon.x, mon.y, mon.width, mon.height
        else:
            # Partial height - anchor at bottom of screen
            height = int(mon.height * self._window_height_percent / 100)
            y = mon.y + (mon.height - height)
            x, width = mon.x, mon.width

        # On Windows with hwnd, use SetWindowPos for precise borderless positioning
        if sys.platform == "win32" and self._hwnd:
            try:
                import ctypes

                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020

                # Withdraw and redraw to force clean positioning
                if force_redraw:
                    self.withdraw()
                    self.update()

                # Use SetWindowPos for exact positioning (bypasses frame adjustments)
                ctypes.windll.user32.SetWindowPos(
                    self._hwnd,
                    None,
                    x,
                    y,
                    width,
                    height,
                    SWP_NOZORDER | SWP_FRAMECHANGED,
                )

                if force_redraw:
                    self.deiconify()

            except Exception:
                # Fallback to tk geometry
                geom = f"{width}x{height}+{x}+{y}"
                self.geometry(geom)
        else:
            # Non-Windows or fallback: use tk geometry
            geom = f"{width}x{height}+{x}+{y}"
            if force_redraw:
                self.withdraw()
                self.geometry(geom)
                self.update()
                self.deiconify()
            else:
                self.geometry(geom)

        # Keep window on top when not full-screen (otherwise it disappears behind other windows)
        if self._window_height_percent < 100:
            self.wm_attributes("-topmost", True)
        else:
            # Full-screen: only use topmost if transparent mode is active
            if not (
                self._subtitle_mode == SUBTITLE_MODE_STATIC and self._transparent_static
            ):
                self.wm_attributes("-topmost", False)

    def set_monitor(self, monitor_index: int):
        """Change the monitor where the subtitle window is displayed."""
        self._monitor_index = monitor_index

        # Reposition window to the new monitor
        self._set_screen_position()
        self.update_idletasks()
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()
        self._update_font()
        self._reposition_subtitles()

    def set_window_height_percent(self, percent: int):
        """Set window height as percentage of screen height (5-100)."""
        self._window_height_percent = max(5, min(100, percent))
        # Use force_redraw to prevent visual glitches during resize
        self._set_screen_position(force_redraw=True)
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()
        self._update_font()
        self._reposition_subtitles()
        # Bring window to front after resize
        self.lift()

    def get_window_height_percent(self) -> int:
        """Get current window height percentage."""
        return self._window_height_percent

    def add_subtitle(self, text: str):
        if not (text or "").strip():
            return

        # In case the window was resized/monitor changed
        self.update_idletasks()
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()

        # In static mode, clear previous subtitle(s) first
        if self._subtitle_mode == SUBTITLE_MODE_STATIC:
            self._clear_all_subtitles()

        # Check if we should use outlined text (transparent static mode)
        use_outline = (
            self._subtitle_mode == SUBTITLE_MODE_STATIC and self._transparent_static
        )

        if use_outline:
            # Create text with per-line background boxes
            text_id, line_items = self._create_outlined_text(
                self.canvas_width / 2,
                self.canvas_height,
                text=text,
            )
            # Calculate total height from all lines
            if line_items and len(line_items) > 1:
                top_bbox = self.canvas.bbox(line_items[0][0])
                bottom_bbox = self.canvas.bbox(line_items[-1][0])
                if top_bbox and bottom_bbox:
                    text_height = bottom_bbox[3] - top_bbox[1]
                else:
                    text_height = 75
            else:
                bbox = self.canvas.bbox(text_id)
                text_height = bbox[3] - bbox[1] if bbox else 75
            self.subtitle_stack.append((text_id, text_height, line_items))
        else:
            # Create normal text
            text_id = self.canvas.create_text(
                self.canvas_width / 2,
                self.canvas_height,
                text=text,
                fill="white",
                font=self.font,
                anchor="s",
                justify="center",
                width=self.canvas.winfo_width() - 75,
            )
            bbox = self.canvas.bbox(text_id)
            text_height = bbox[3] - bbox[1] if bbox else 75
            self.subtitle_stack.append((text_id, text_height, None))

        # Limit subtitles in stack mode only
        if self._subtitle_mode == SUBTITLE_MODE_STACK:
            if len(self.subtitle_stack) > self.max_subtitles:
                old_item = self.subtitle_stack.pop(0)
                old_id = old_item[0]
                old_line_items = old_item[2] if len(old_item) > 2 else None
                self.canvas.delete(old_id)
                if old_line_items:
                    for line_text_id, box_id in old_line_items:
                        if line_text_id:
                            self.canvas.delete(line_text_id)
                        if box_id:
                            self.canvas.delete(box_id)

        # Reposition based on mode
        if self._subtitle_mode == SUBTITLE_MODE_CONTINUOUS:
            # In continuous mode, position new text below the lowest existing text
            # Find the lowest (highest y value) text position
            lowest_y = self.canvas_height - self.margin_bottom
            for item in self.subtitle_stack[:-1]:  # Exclude the one we just added
                existing_id = item[0]
                existing_height = item[1]
                coords = self.canvas.coords(existing_id)
                if coords:
                    # coords[1] is the y position (anchor="s" means bottom of text)
                    text_bottom = coords[1]
                    # The top of next text should be below this text's bottom + spacing
                    potential_y = text_bottom + text_height + self.line_spacing
                    if potential_y > lowest_y:
                        lowest_y = potential_y

            # Position new text at the lowest point (may be below screen, that's OK)
            self.canvas.coords(text_id, self.canvas_width / 2, lowest_y)
        else:
            self._reposition_subtitles()

    def _start_continuous_scroll(self):
        """Start the continuous upward scroll animation."""
        self._animate_continuous_scroll()

    def _animate_continuous_scroll(self):
        """Animation frame for continuous scroll mode."""
        if self._subtitle_mode != SUBTITLE_MODE_CONTINUOUS:
            return

        items_to_remove = []

        for i, item in enumerate(self.subtitle_stack):
            text_id = item[0]
            text_height = item[1]
            # Move text upward using current scroll speed
            self.canvas.move(text_id, 0, -self._scroll_speed)

            # Check if text is completely off screen (above top)
            coords = self.canvas.coords(text_id)
            if coords:
                y = coords[1]
                # If the bottom of the text is above the screen, remove it
                if y + text_height < 0:
                    items_to_remove.append(i)

        # Remove items that scrolled off screen (in reverse order to preserve indices)
        for i in reversed(items_to_remove):
            item = self.subtitle_stack.pop(i)
            text_id = item[0]
            self.canvas.delete(text_id)

        # Schedule next frame
        self._scroll_animation_id = self.after(
            SCROLL_INTERVAL_MS, self._animate_continuous_scroll
        )

    def _reposition_subtitles(self):
        if not self.subtitle_stack:
            return

        import tkinter.font as tkfont

        current_y = self.canvas_height - self.margin_bottom
        padding_x = 20
        padding_y = 8
        line_gap = 4

        for i in range(len(self.subtitle_stack) - 1, -1, -1):
            item = self.subtitle_stack[i]
            text_id = item[0]
            text_height = item[1]
            line_items = item[2] if len(item) > 2 else None

            if line_items:
                # Reposition each line from bottom to top
                font_obj = tkfont.Font(font=self.font)
                line_height = font_obj.metrics("linespace")
                line_y = current_y

                for line_text_id, box_id in reversed(line_items):
                    # Move line text
                    self.canvas.coords(line_text_id, self.canvas_width / 2, line_y)

                    # Update box position
                    if box_id:
                        bbox = self.canvas.bbox(line_text_id)
                        if bbox:
                            self.canvas.coords(
                                box_id,
                                bbox[0] - padding_x,
                                bbox[1] - padding_y,
                                bbox[2] + padding_x,
                                bbox[3] + padding_y,
                            )

                    # Set text color
                    if i == len(self.subtitle_stack) - 1:
                        self.canvas.itemconfig(line_text_id, fill="white")
                    else:
                        self.canvas.itemconfig(line_text_id, fill="gray85")

                    line_y -= line_height + line_gap
            else:
                # Normal text (non-outlined)
                self.canvas.coords(text_id, self.canvas_width / 2, current_y)

                if i == len(self.subtitle_stack) - 1:
                    self.canvas.itemconfig(text_id, fill="white")
                else:
                    self.canvas.itemconfig(text_id, fill="gray85")

            current_y -= text_height + self.line_spacing
