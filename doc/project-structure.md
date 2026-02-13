# Project Structure

```
├── main.py                  # Entry point
├── app_controller.py        # Thread lifecycle controller (start/stop pipeline)
├── config.py                # Static configuration and constants
├── requirements.txt         # Python dependencies
├── pytest.ini               # Pytest configuration
├── MinbarLive.spec          # PyInstaller build spec
│
├── data/                            # Static data files
│   ├── embeddings/
│   │   └── quran_embeddings.json    # Precomputed verse embeddings (mini-RAG DB)
│   └── translations/
│       ├── quran/                   # Arabic → translation verse mappings
│       │   ├── de.json              # German (Bubenheim & Elyas)
│       │   ├── en.json              # English (Hilali & Khan)
│       │   ├── tr.json              # Turkish (Rwwad Center)
│       │   ├── sq.json              # Albanian (Sherif Ahmeti)
│       │   └── bs.json              # Bosnian (Rwwad Center)
│       ├── athan/                   # Athan phrase translations
│       │   ├── de.json              # German
│       │   ├── en.json              # English
│       │   ├── tr.json              # Turkish
│       │   ├── sq.json              # Albanian
│       │   └── bs.json              # Bosnian
│       ├── gui/                     # GUI interface translations
│       │   ├── de.json              # German
│       │   ├── en.json              # English
│       │   ├── ar.json              # Arabic
│       │   ├── bs.json              # Bosnian
│       │   ├── sq.json              # Albanian
│       │   └── tr.json              # Turkish
│       └── footer_translations.json # Disclaimer footer in multiple languages
│
├── audio/                   # Audio capture and processing
│   ├── capture.py           # Ring buffer, silence detection
│   └── writer.py            # Async file writing
│
├── translation/             # Translation pipeline
│   ├── buffering.py         # Processing strategies (chunk-based, semantic)
│   ├── dictionary.py        # Multi-language dictionary loading, fuzzy search
│   ├── rag.py               # Embedding-based Quran matching
│   └── translator.py        # GPT translation with RAG hints
│
├── gui/                     # User interface
│   ├── app_gui.py           # Control window (settings, logs)
│   └── subtitle_window.py   # Full-screen subtitle display
│
├── tests/                   # Unit tests
│   ├── test_context_manager.py  # Adaptive context management
│   ├── test_dictionary.py       # Arabic normalization, Athan matching
│   ├── test_json_helpers.py     # JSON loading edge cases
│   ├── test_keyring_storage.py  # Secure API key storage
│   ├── test_rag.py              # Cosine similarity, RAG availability
│   ├── test_retry.py            # Exponential backoff for API calls
│   ├── test_settings.py         # Settings dataclass, language codes
│   └── test_silence_detection.py # Audio silence detection
│
├── notebooks/               # Development notebooks
│   ├── Build_Quran_EmbeddingSpace.ipynb  # Generate quran_embeddings.json
│   ├── build_quran_dict.py               # Rebuild translation dictionaries
│   └── test_translation_and_rag.ipynb    # Interactive RAG & translation testing
│
└── utils/                   # Utilities
    ├── api_key_manager.py   # API key prompting and storage
    ├── app_paths.py         # Per-user writable app data directory
    ├── context_manager.py   # Adaptive context with async summarization
    ├── history.py           # Transcription/translation logging
    ├── json_helpers.py      # JSON file I/O
    ├── keyring_storage.py   # Secure API key storage (OS keychain)
    ├── logging.py           # Thread-safe logging
    ├── openai_client.py     # OpenAI client singleton
    ├── retry.py             # Exponential backoff for API calls
    └── settings.py          # User preferences (language, font, monitor, etc.)
```

## Runtime Files

Runtime files are written to a per-user app data folder:

- **Windows**: `%APPDATA%\MinbarLive\`
- **macOS**: `~/Library/Application Support/MinbarLive/`
- **Linux**: `~/.local/share/MinbarLive/`

Contents:

- `history/` - Transcript + translation logs
- `logs/` - Daily application log files (e.g., `2026-02-13.log`)
- `recordings/` - Temporary WAV segments
- `settings.json` - Language preferences, font size, monitor index (NOT the API key)

> **Note:** API keys are stored securely in your OS keychain, not in settings.json.
