"""API key management: prompting, validation, and storage."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from utils.logging import log
from utils.settings import get_saved_api_key, set_saved_api_key, delete_saved_api_key
from utils.openai_client import set_api_key, has_api_key


def ensure_api_key_on_startup(
    root: tk.Tk,
    on_close: Callable[[], None],
    on_change_key: Callable[[bool], None],
) -> None:
    """
    Ensure an API key is configured on startup.

    Checks saved key first, then environment variable, then prompts user.

    Args:
        root: The Tk root window (for scheduling).
        on_close: Callback to close the app if key is required but not provided.
        on_change_key: Callback to prompt for key (receives startup=True/False).
    """
    saved = (get_saved_api_key() or "").strip()
    if saved:
        set_api_key(saved)
        return

    # Try environment variable / .env
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except ImportError:
        log("python-dotenv not installed, skipping .env file.", level="DEBUG")
    except Exception as e:
        log(f"Failed to load .env file: {e}", level="DEBUG")

    env_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if env_key:
        set_api_key(env_key)
        log("Using OPENAI_API_KEY from environment.", level="INFO")
        return

    # No saved key → ask once (first run)
    on_change_key(True)


def prompt_for_api_key(
    root: tk.Tk,
    startup: bool,
    on_close: Callable[[], None],
) -> Optional[str]:
    """
    Prompt user for an API key.

    Args:
        root: The Tk root window.
        startup: Whether this is the first-run prompt.
        on_close: Callback to close the app if cancelled on startup.

    Returns:
        The entered API key, or None if cancelled/empty.
    """
    prompt = "Paste your OpenAI API key:" if startup else "Enter a new OpenAI API key:"
    
    # Create a custom larger dialog
    dialog = tk.Toplevel(root)
    dialog.title("OpenAI API Key")
    dialog.geometry("500x180")
    dialog.resizable(True, True)
    dialog.transient(root)
    dialog.grab_set()
    
    # Center the dialog on screen
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() - 500) // 2
    y = (dialog.winfo_screenheight() - 180) // 2
    dialog.geometry(f"500x180+{x}+{y}")
    
    # Ensure the popup is always on top
    try:
        dialog.wm_attributes("-topmost", True)
    except Exception:
        pass
    
    # Label
    label = tk.Label(dialog, text=prompt, font=("Segoe UI", 11))
    label.pack(pady=(20, 10))
    
    # Entry field (larger)
    entry = tk.Entry(dialog, show="*", font=("Segoe UI", 12), width=50)
    entry.pack(pady=10, padx=20, fill=tk.X)
    entry.focus_set()
    
    result = {"key": None}
    
    def on_ok():
        result["key"] = entry.get()
        dialog.destroy()
    
    def on_cancel():
        result["key"] = None
        dialog.destroy()
    
    # Buttons frame
    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=20)
    
    ok_btn = tk.Button(btn_frame, text="OK", command=on_ok, width=12, font=("Segoe UI", 10))
    ok_btn.pack(side=tk.LEFT, padx=10)
    
    cancel_btn = tk.Button(btn_frame, text="Cancel", command=on_cancel, width=12, font=("Segoe UI", 10))
    cancel_btn.pack(side=tk.LEFT, padx=10)
    
    # Bind Enter key to OK
    entry.bind("<Return>", lambda e: on_ok())
    dialog.bind("<Escape>", lambda e: on_cancel())
    
    # Handle window close button
    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    
    dialog.wait_window()
    key = result["key"]

    if key is None:
        if startup:
            messagebox.showerror(
                "API key required", "An API key is required to use this app."
            )
            root.after(100, on_close)
        return None

    key = key.strip()
    if not key:
        messagebox.showerror("Invalid key", "Key cannot be empty.")
        if startup:
            root.after(
                100, lambda: prompt_for_api_key(root, startup=True, on_close=on_close)
            )
        return None

    # Validate API key format (OpenAI keys start with 'sk-')
    if not key.startswith("sk-"):
        messagebox.showwarning(
            "Invalid format",
            "OpenAI API keys typically start with 'sk-'. "
            "The key will be saved, but may not work.",
        )
        log(f"API key format warning: key does not start with 'sk-'", level="WARNING")

    # Save and set the key
    set_saved_api_key(key)
    set_api_key(key)
    log("API key saved.", level="INFO")
    messagebox.showinfo("Saved", "API key saved.")
    return key


def remove_api_key(is_running: bool) -> bool:
    """
    Remove the saved API key.

    Args:
        is_running: Whether the app is currently running (blocks removal).

    Returns:
        True if key was removed, False otherwise.
    """
    if is_running:
        messagebox.showwarning("Stop first", "Stop the app before removing the key.")
        return False

    if not messagebox.askyesno("Remove key", "Remove the saved API key?"):
        return False

    delete_saved_api_key()
    set_api_key(None)
    log("API key removed.", level="INFO")
    messagebox.showinfo("Removed", "API key removed.")
    return True
