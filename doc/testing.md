# Testing

The project includes a comprehensive test suite using pytest.

## Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_dictionary.py

# Run with coverage (requires pytest-cov)
python -m pytest --cov=.
```

## Test Coverage

| Test File                   | Coverage Area                              |
| --------------------------- | ------------------------------------------ |
| `test_context_manager.py`   | Adaptive context management                |
| `test_dictionary.py`        | Arabic normalization, Athan fuzzy matching |
| `test_json_helpers.py`      | JSON loading, edge cases                   |
| `test_keyring_storage.py`   | Secure API key storage                     |
| `test_rag.py`               | Cosine similarity, RAG availability        |
| `test_retry.py`             | Exponential backoff for API calls          |
| `test_settings.py`          | Settings dataclass, language codes         |
| `test_silence_detection.py` | Audio silence detection                    |
