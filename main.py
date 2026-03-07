"""MinbarLive - Main Entry Point."""

import argparse
import sys

# Set Windows taskbar icon (must be done before tkinter imports)
# Note: sys.platform is always "win32" on Windows, even on 64-bit systems
if sys.platform == "win32":
    try:
        import ctypes

        # This tells Windows to use our app icon in the taskbar instead of Python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "MinbarLive.MinbarLive"
        )
    except (AttributeError, OSError):
        pass  # Not on Windows or windll unavailable


def main() -> None:
    parser = argparse.ArgumentParser(description="MinbarLive - Real-time translation")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Set log level BEFORE importing modules that use logging
    if args.debug:
        import utils.logging as logging_module

        logging_module.LOG_LEVEL = "DEBUG"

    from config import ensure_directories
    from app_controller import AppController
    from gui.app_gui import AppGUI
    from utils.cleanup import run_cleanup

    # Create necessary directories at startup
    ensure_directories()

    # Purge stale log / history files
    run_cleanup()

    controller = AppController()
    gui = AppGUI(controller)
    gui.mainloop()


if __name__ == "__main__":
    main()
