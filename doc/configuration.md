# Configuration

## User Settings (GUI)

These settings are configurable from the control panel and saved between sessions:

| Setting         | Description                                   |
| --------------- | --------------------------------------------- |
| GUI Language    | Interface language (DE, EN, BS, SQ, TR)       |
| Source Language | Spoken language (Arabic, Turkish, Urdu, etc.) |
| Target Language | Translation output (35+ languages)            |
| Subtitle Mode   | Continuous scroll, Stack, or Static display   |
| Transparent     | Transparent overlay for static mode           |
| Font Size       | Adjustable subtitle font size                 |
| Scroll Speed    | Speed for continuous mode (0.5x - 5x)         |
| Input Device    | Audio input source selection                  |
| Subtitle Screen | Monitor for subtitle display                  |

### GUI Languages

The control panel interface is available in 6 languages:

| Code | Language |
| ---- | -------- |
| de   | Deutsch  |
| en   | English  |
| ar   | العربية  |
| bs   | Bosanski |
| sq   | Shqip    |
| tr   | Türkçe   |

Select your preferred language from the dropdown in the top-right corner. Changes apply immediately without restart.

### Advanced Settings

| Setting             | Default            | Description                                         |
| ------------------- | ------------------ | --------------------------------------------------- |
| Translation Model   | GPT-4o Mini        | OpenAI model for translation (affects cost/quality) |
| Transcription Model | GPT-4o Transcribe  | OpenAI model for speech-to-text                     |
| Processing Strategy | Semantic buffering | How audio segments are grouped before translation   |

**Processing Strategy Options:**

- **Semantic buffering** (default): Waits for complete sentences before translating. Better quality, slight delay.
- **Chunk-based**: Translates each audio segment immediately. Faster feedback, may cut sentences.

## Technical Constants (config.py)

Edit `config.py` to adjust:

| Parameter                   | Default | Description                                   |
| --------------------------- | ------- | --------------------------------------------- |
| `DURATION`                  | 12s     | Length of each audio segment                  |
| `OVERLAP`                   | 2s      | Overlap between segments                      |
| `FS`                        | 16000   | Sample rate                                   |
| `SEMANTIC_MAX_CHUNKS`       | 3       | Max segments to buffer before forcing flush   |
| `SEMANTIC_MAX_SECONDS`      | 10      | Max seconds to buffer before forcing flush    |
| `RAG_MIN_SIMILARITY`        | 0.60    | Minimum cosine similarity for Quran matching  |
| `RAG_TOP_K`                 | 5       | Max number of Quran candidates per segment    |
| `ATHAN_MATCH_THRESHOLD`     | 0.75    | Minimum fuzzy match score for Athan detection |
| `CONTEXT_RECENT_RAW_COUNT`  | 3       | Raw transcription segments to keep            |
| `CONTEXT_SUMMARIZE_EVERY_N` | 10      | Segments between rolling summary updates      |
| `CONTEXT_HOURLY_INTERVAL`   | 3600    | Seconds between hourly summary snapshots      |

## Retry Configuration (utils/retry.py)

API calls automatically retry on transient failures (rate limits, timeouts, connection errors):

| Parameter     | Default | Description                             |
| ------------- | ------- | --------------------------------------- |
| `max_retries` | 3       | Maximum retry attempts                  |
| `base_delay`  | 1.0s    | Initial delay between retries           |
| `max_delay`   | 30.0s   | Maximum delay (caps exponential growth) |

Retries use exponential backoff with jitter to prevent thundering herd problems.

## OpenAI Models (config.py)

The following models are hardcoded in `config.py`. If OpenAI deprecates or renames these models, you'll need to update them:

| Constant              | Current Value            | Purpose                      |
| --------------------- | ------------------------ | ---------------------------- |
| `TRANSCRIPTION_MODEL` | `gpt-4o-transcribe`      | Speech-to-text transcription |
| `TRANSLATION_MODEL`   | `gpt-4o-mini`            | Text translation             |
| `EMBEDDING_MODEL`     | `text-embedding-3-large` | Vector embeddings for RAG    |

> **Note:** If you change `EMBEDDING_MODEL`, you must regenerate `quran_embeddings.json` using the notebook in `notebooks/`.
