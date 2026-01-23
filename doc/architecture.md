# Architecture

## System Overview

```
                              ┌─────────────────────────────────────────────────────────┐
                              │                    App Controller                       │
                              │              (Thread Lifecycle Manager)                 │
                              └─────────────────────────────────────────────────────────┘
                                       │              │                │
                    ┌──────────────────┘              │                └──────────────────┐
                    ▼                                 ▼                                   ▼
          ┌─────────────────┐              ┌───────────────────┐              ┌─────────────────┐
          │  Audio Capture  │  ─────────▶ │  Transcription    │  ─────────▶  │   Translation   │
          │  (Ring Buffer)  │              │(GPT-4o-transcribe)│              │   (RAG + GPT)   │
          └─────────────────┘              └───────────────────┘              └────────┬────────┘
                                                    │                           ▲      │
                                                    │    context                │      │
                                                    ▼      ┌────────────────────┘      │
                                           ┌──────────────────┐                        │
                                           │ Context Manager  │                        │
                                           │ (Async Summaries)│                        │
                                           └──────────────────┘                        │
                                                                                       ▼
                              ┌─────────────────┐                            ┌─────────────────┐
                              │   Control GUI   │   ────────────────────▶   │  Subtitle GUI   │
                              │ (Settings, Logs)│                            │  (Full Screen)  │
                              └─────────────────┘                            └─────────────────┘
```

## Data Flow

1. **Audio Capture** records microphone input into a ring buffer
2. **Transcription** converts audio segments to text via OpenAI API
3. **Processing Strategy** buffers transcriptions (semantic) or passes through (chunk)
4. **Context Manager** receives transcriptions, provides context back to Translation (async)
5. **Translation** uses RAG + context + GPT to produce the final translation
6. **Subtitle GUI** displays translations full-screen
7. **Control GUI** provides settings, logs, and start/stop controls

## Processing Strategies

The app supports two strategies for grouping transcriptions before translation:

### Semantic Buffering (Default)

- Waits for complete sentences before translating
- Triggers flush when: sentence-ending punctuation detected, 3+ segments buffered, or 10s timeout
- Better translation quality for religious content
- Slight delay (5-15 seconds) before subtitles appear

### Chunk-based

- Each audio segment is translated immediately
- Faster subtitle display
- May split sentences mid-thought, reducing translation quality

> **Recommendation:** Use Semantic Buffering for sermons/lectures where quality matters. Use Chunk-based only if immediate feedback is critical.

## Adaptive Context Management

For long sessions (1-4+ hours), the app uses intelligent context management:

- **Recent segments (last 3)**: Kept raw for immediate disambiguation
- **Rolling summary**: Updated every ~10 segments (async, no delay)
- **Hourly summaries**: Long-term context compressed to ~20 words each

This keeps context under ~1500 tokens while maintaining session continuity.

### What the Translation LLM receives for each segment

```
1. Source Text: Current transcription to translate
2. Context:
   - [Session overview: Hr1: ... | Hr2: ...]     ← Hourly summaries (if >1hr)
   - [Recent topics: ...]                         ← Rolling summary (~50 words)
   - [Last segments: seg1 / seg2 / seg3]          ← Last 3 raw transcriptions
3. Quran Hints: Matched verses from RAG (if any)
```

The context helps disambiguate unclear words without bloating the prompt.
