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
3. **Context Manager** receives transcriptions, provides context back to Translation (async)
4. **Translation** uses RAG + context + GPT to produce the final translation
5. **Subtitle GUI** displays translations full-screen
6. **Control GUI** provides settings, logs, and start/stop controls

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
