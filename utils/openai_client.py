"""OpenAI client singleton with runtime-configurable API key."""

from __future__ import annotations

from typing import Optional

from openai import OpenAI


_client: Optional[OpenAI] = None
_api_key: Optional[str] = None


def set_api_key(api_key: Optional[str]) -> None:
    """Set the API key and reset the client instance."""
    global _client, _api_key
    _api_key = (api_key or "").strip() or None
    _client = None


def has_api_key() -> bool:
    return bool((_api_key or "").strip())


def get_client() -> OpenAI:
    """Get (or create) an OpenAI client for the current API key."""
    global _client
    if _client is None:
        if not has_api_key():
            raise RuntimeError("OpenAI API key is not configured.")
        _client = OpenAI(api_key=_api_key)
    return _client
