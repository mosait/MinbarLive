<div align="center">
    <a href="https://github.com/mosait/MinbarLive" />
        <img alt="Logo" height="200px" src="./public/MinbarLive2.png">
    </a>
</div>

# MinbarLive - Islamic Live Translation

Real-time translation system for mosque lectures and prayers, supporting multiple languages.

## Overview

This application captures live audio from a microphone, transcribes speech using OpenAI's GPT-4o-transcribe, and translates it using GPT-4o-mini. Translations are displayed as subtitles on a full-screen GUI.

> **⚠️ Language Note:** The primary development and testing focus was **Arabic → German**. While the app supports 15+ source languages and 35+ target languages, other language combinations have not been extensively tested. The Quran and Athan dictionaries are available in **German, English, Turkish, Albanian, and Bosnian**. Contributions for additional language support are welcome!

### Key Features

- Real-time audio capture with automatic silence detection
- Multi-language support (15+ source, 35+ target languages)
- Semantic buffering for complete sentence translation (configurable)
- RAG-enhanced translation using precomputed Quran verse embeddings
- Dictionary matching for Athan phrases
- Three subtitle modes: Continuous scroll, stacking, or static display
- Multi-monitor support with transparent overlay option
- Secure API key storage using OS keychain
- Automatic retry with exponential backoff

📚 **More details:** See the [doc/](doc/) folder for architecture, configuration, and data file documentation.

## ⚠️ API Cost Warning

This application makes continuous API calls to OpenAI while running. **You will be charged for usage.**

| Usage Pattern                   | Transcription | Translation | Embeddings | **Total**        |
| ------------------------------- | ------------- | ----------- | ---------- | ---------------- |
| 1 hour session                  | ~$0.36        | ~$0.10      | ~$0.05     | **~$0.50**       |
| Weekly Friday prayer (1 hr × 4) | ~$1.44        | ~$0.40      | ~$0.20     | **~$2.00/month** |

> **Note:** Prices may change. Check [OpenAI Pricing](https://openai.com/pricing) for current rates. Set a [usage limit](https://platform.openai.com/account/limits) in your OpenAI account to avoid surprises.

## Setup

### Prerequisites

- Python 3.10+ (Option B only)
- OpenAI API key
- Audio input device (microphone or virtual audio cable)

### Option A: Use the EXE (recommended)

1. Download the latest EXE: [Click here](https://github.com/mosait/MinbarLive/releases)
2. Run `MinbarLive.exe`
3. Paste your OpenAI API key when prompted - Tutorial [EN](https://youtu.be/OB99E7Y1cMA)/[DE](https://youtu.be/SISlgzB_qpQ?si=v3yiOK0-1C3GxYaf)
4. It's Running!

> **Windows SmartScreen:** You may see a warning because the EXE is not code-signed. Click "More info" → "Run anyway".

> **Platform Note:** The EXE is Windows-only. Linux users have had success with Wine. macOS is not supported via EXE.

### Option B: Build it yourself (Python)

```bash
git clone https://github.com/mosait/MinbarLive.git
cd MinbarLive
python -m venv .venv
.\.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
python main.py
```

Set your OpenAI API key via `.env` file or let the app prompt you on first run (stored securely in OS keychain).

Two windows will appear:

- **Control Panel** - Start/Stop, settings, API key management, logs
- **Subtitles** - Full-screen translated text display

Press `Escape` to exit.

## Mirroring/Streaming/Record with OBS

Easiest way to mirror, stream or record with camera + subtitles using [OBS Studio](https://obsproject.com/):

1. **Add your camera**: Sources → Add → Video Capture Device
2. **Add the subtitle window**: Sources → Add → Window Capture → Select `[MinbarLive.exe]: MinbarLive Subtitles`
3. **Position subtitles at bottom**: Right-click the subtitle source → Transform → Edit Transform → Set "Positional Alignment" to **Bottom Center**
4. **Display on another monitor**: Right-click the canvas → Open Preview Projector → Select your monitor (press `Escape` to exit)

This overlays the live translations on your camera feed for Mirroring, YouTube, Zoom, or recording.

## Runtime Files

Runtime files are written to a per-user app data folder:

- **Windows**: `%APPDATA%\MinbarLive\`
- **macOS**: `~/Library/Application Support/MinbarLive/`
- **Linux**: `~/.local/share/MinbarLive/`

## Documentation

| Document                                             | Description                                            |
| ---------------------------------------------------- | ------------------------------------------------------ |
| [doc/architecture.md](doc/architecture.md)           | System architecture and data flow                      |
| [doc/project-structure.md](doc/project-structure.md) | Full project tree and file descriptions                |
| [doc/configuration.md](doc/configuration.md)         | All configurable settings and constants                |
| [doc/data-files.md](doc/data-files.md)               | Quran/Athan translations, embeddings, adding languages |
| [doc/testing.md](doc/testing.md)                     | Running tests and coverage                             |

## Feedback

- **GitHub Issues**: [Open an issue](https://github.com/mosait/MinbarLive/issues)
- **Google Forms**: [Submit feedback](https://forms.gle/T7hvU4yEbVRM4PmWA) anonymously

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GPL-3.0. See `LICENSE`.
