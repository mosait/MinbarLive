# Data Files

## Quran Translation Source

The translation database is built programmatically via public APIs:

- **Arabic text** (without diacritics) from `quranapi.pages.dev`
- **Translations** from `quranenc.com`

### Available Quran Translations

| Language | File      | Translation Key       | Source            |
| -------- | --------- | --------------------- | ----------------- |
| German   | `de.json` | `german_bubenheim`    | Bubenheim & Elyas |
| English  | `en.json` | `english_hilali_khan` | Hilali & Khan     |
| Turkish  | `tr.json` | `turkish_rwwad`       | Rwwad Center      |
| Albanian | `sq.json` | `albanian_nahi`       | Sherif Ahmeti     |
| Bosnian  | `bs.json` | `bosnian_rwwad`       | Rwwad Center      |

### Available Athan Translations

| Language | File      |
| -------- | --------- |
| German   | `de.json` |
| English  | `en.json` |
| Turkish  | `tr.json` |
| Albanian | `sq.json` |
| Bosnian  | `bs.json` |

To add a new language, use `notebooks/build_quran_dict.py` with a translation key from [quranenc.com](https://quranenc.com).

> **Note:** For languages without a curated dictionary, the app falls back to GPT's translation capabilities. Contributions for additional language sources are welcome!

> **Note on Hadith:** Unfortunately, we could not find a suitable open database for Hadith translations with the same quality and accessibility. Contributions for Hadith support are welcome!

---

## quran_embeddings.json (Mini-RAG Database)

This file contains precomputed vector embeddings for all 6,236 Quran verses. Instead of using an external vector database (like Pinecone, Weaviate, or ChromaDB), we store embeddings directly in a JSON file as a lightweight "mini-RAG" solution.

### Why this approach?

- No external database dependencies required
- The dataset is small enough (~6,236 verses) to fit in memory
- Simple deployment - just a single JSON file
- Works offline once loaded

### Structure

```json
{
  "Arabic verse text": [0.123, -0.456, ...],  // 3072-dim embedding vector
  ...
}
```

### How it works

1. Audio is transcribed to Arabic text
2. The transcribed text is embedded using OpenAI's `text-embedding-3-large` model
3. **Cosine similarity** is computed between the transcription embedding and all stored verse embeddings
4. Verses with similarity above `RAG_MIN_SIMILARITY` (default: 0.60) are retrieved
5. Top-K matches (default: 5) are passed to GPT as translation hints
6. GPT uses these hints to produce more accurate translations, especially for Quranic verses

This approach ensures that when Quran is recited, the exact Bubenheim & Elyas translation is used rather than GPT's own translation.

---

## Translation Dictionaries

Translation files are organized by language under `data/translations/`:

```
data/translations/
├── quran/
│   ├── de.json    # German (Bubenheim & Elyas)
│   ├── en.json    # English (Hilali & Khan)
│   ├── tr.json    # Turkish (Rwwad Center)
│   ├── sq.json    # Albanian (Sherif Ahmeti)
│   └── bs.json    # Bosnian (Rwwad Center)
├── athan/
│   ├── de.json    # German
│   ├── en.json    # English
│   ├── tr.json    # Turkish
│   ├── sq.json    # Albanian
│   └── bs.json    # Bosnian
└── footer_translations.json
```

### Adding a new language

1. Create `data/translations/quran/{lang_code}.json` with Arabic → translation mappings
   - Use `notebooks/build_quran_dict.py` with the appropriate translation key from quranenc.com
2. Create `data/translations/athan/{lang_code}.json` for Athan phrases
3. The system will automatically use these when the target language matches

### footer_translations.json

Contains the disclaimer footer text in multiple languages, displayed at the bottom of the subtitle window.

---

## Regenerating Embeddings

If you need to regenerate `data/embeddings/quran_embeddings.json` (e.g., after changing the embedding model), use the notebook:

- [notebooks/Build_Quran_EmbeddingSpace.ipynb](../notebooks/Build_Quran_EmbeddingSpace.ipynb)

**Requirements:**

- Set your `OPENAI_API_KEY` environment variable
- Ensure `data/translations/quran/de.json` exists (source of Arabic verses)
- Run all cells in the notebook (takes ~10-15 minutes for 6,236 verses)
