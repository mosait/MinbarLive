"""
Main translation logic using dictionary matching, RAG, and GPT.
Supports dynamic target language configuration.

Same-language mode (source == target):
- Skips GPT translation entirely
- Returns transcription directly (Whisper output)
- For Arabic: may return canonical phrases from dictionary
"""

from __future__ import annotations

from config import ATHAN_MATCH_THRESHOLD
from utils.logging import log
from utils.openai_client import get_client
from utils.retry import retry_with_backoff
from utils.settings import (
    load_settings,
    get_target_language_code,
    DEFAULT_TRANSLATION_MODEL,
    FALLBACK_TRANSLATION_MODELS,
)
from translation.dictionary import fuzzy_match_athan, has_athan_translation
from translation.rag import match_quran_rag_multi


def _get_translation_model() -> str:
    """Get the configured translation model from settings."""
    return load_settings().translation_model or DEFAULT_TRANSLATION_MODEL


def _get_source_language() -> str:
    """Get the configured source language from settings."""
    return load_settings().source_language or "Arabic"


def _get_target_language() -> str:
    """Get the configured target language from settings."""
    return load_settings().target_language or "German"


def _build_system_prompt(source_lang: str, target_lang: str) -> str:
    """Build a system prompt for translating Islamic content to the target language."""
    return f"""
    You are a professional translator specializing in Islamic religious content 
    including sermons (khutbah), Quran recitations, Hadith, and classical Arabic rhetoric.

    Your task is to translate from {source_lang} into {target_lang} in a way that is:
    - theologically precise,
    - faithful to meaning,
    - and natural and fluent in the target language.

    Important principles:
    - Preserve ALL meanings and religious concepts.
    - Do NOT translate word-for-word unless the structure is natural in {target_lang}.
    - You MAY adapt rhetorical structure, sentence flow, and repetition so that the translation
    sounds natural and appropriate for religious speech in {target_lang}.
    - Arabic rhetorical repetition or parallel phrasing may be stylistically merged
    if no meaning is lost.
    - Use target-language-appropriate religious style and register.

    Additional guidelines:
    - The content is Sunni Islamic.
    - Preserve Islamic terminology (Allah, Umma, Sunnah, Hadith, Iblis, Jinn, Salah, etc.);
    transliterate rather than translate these terms.
    - Use ONLY these two standard Unicode honorific symbols:
      - ﷺ after mentioning Prophet Muhammad (sallallahu alayhi wa sallam)
      - ﷻ after mentioning Allah (jalla jalaluhu)
    - Do NOT use Arabic script for other honorifics (e.g., radiyallahu anhu, rahimahullah, 
      alayhi salam). Either transliterate or translate them.
    - Handle transcription errors conservatively; correct only if meaning is clearly distorted.
    - Prefer 'Allah' over local equivalents for God.
    - Output ONLY the translation. No comments, no explanations, no markdown.
    """


def _build_user_prompt(
    text: str, context: str, quran_hint: str, source_lang: str, target_lang: str
) -> str:
    """Build the user prompt with text, context, and optional Quran hints."""
    prompt = f"""You will receive a short transcript from a mosque audio stream under "Source Text"
    and optionally previous context under "Context".

    Your task:
    - Translate ONLY the text in the "Source Text" section into {target_lang}.
    - The primary source language is {source_lang}, but Arabic Quran verses or religious phrases may appear.
    - Use the Context ONLY to resolve unclear references or pronouns; do NOT translate or repeat it.
    - Preserve all meanings and religious content of the source text.
    - You may adjust sentence structure, flow, and repetition so the translation
    sounds natural and fluent in {target_lang}.
    - Do NOT invent additional sentences, Quran verses, or Hadith.
    - Do NOT omit any meaning.
    - Use a clear, idiomatic, and listener-friendly {target_lang} style
    appropriate for religious speech.
    - Preserve religious terminology correctly.
    - Output ONLY the translated {target_lang} text — no explanations, no comments.
    """

    if quran_hint:
        prompt += "\n\n" + quran_hint

    if context:
        prompt += f"""

Context (for understanding only, do NOT translate or repeat):
{context}"""

    prompt += f"""

Source Text (translate ONLY this section into {target_lang}):
{text}

{target_lang} Translation:"""

    return prompt


def _build_quran_hint(quran_matches: list, target_lang: str) -> str:
    """Build the Quran RAG hint section for the prompt."""
    if not quran_matches:
        return ""

    blocks = []
    for idx, (score, ar_quran, ref_trans) in enumerate(quran_matches, start=1):
        # Note: ref_trans contains the stored reference translation (currently German)
        # For other languages, GPT will adapt based on the Arabic original
        blocks.append(
            f"""
Candidate {idx} (Score={score:.3f}):

Arabic Quran verse (candidate):
{ar_quran}

Reference translation (use as guide, adapt to {target_lang} if needed):
{ref_trans}
        """.strip()
        )

    return (
        f"""
NOTE – POSSIBLE QURAN VERSES:

The source text MAY contain Arabic Quran verses. The verses below are candidates detected via semantic matching.
Rules for usage:

- Use the provided reference translation ONLY if you recognize that this verse actually appears 
  (completely or very clearly) in the "Source Text" section.
- If the corresponding verse does NOT appear in the current section, do NOT include its translation.
- Do NOT add additional Quran verses from this list if they don't appear in the current text.
- Adapt the reference translation to natural {target_lang} if needed, but preserve the meaning exactly.

Candidates:
""".strip()
        + "\n\n"
        + "\n\n".join(blocks)
    )


def translate_text(text: str, context: str = "") -> str:
    """
    Translate mosque audio transcription to the configured target language.

    Pipeline:
    1. Same-language mode: Return transcription directly (no GPT)
    2. Check for Athan phrases (direct dictionary match)
    3. Find potential Quran verses via RAG
    4. Use GPT for final translation with Quran hints

    Args:
        text: Transcribed text (may be Arabic, Turkish, Urdu, or mixed).
        context: Previous transcriptions for context (not translated).

    Returns:
        Translation in the configured target language, or transcription for same-language mode.
    """
    txt = (text or "").strip()
    if not txt:
        return ""

    source_lang = _get_source_language()
    target_lang = _get_target_language()
    target_lang_code = get_target_language_code(target_lang) or "de"

    # --- 0) Same-language mode: skip translation ---
    if source_lang == target_lang:
        log(
            f"Same-language mode ({source_lang}): returning transcription directly",
            level="INFO",
        )

        # For Arabic, try to match canonical Athan phrases
        if target_lang_code == "ar":
            score_athan, athan_canonical, ar_athan = fuzzy_match_athan(txt, "ar")
            if score_athan >= ATHAN_MATCH_THRESHOLD and athan_canonical:
                log(
                    f"Athan canonical match: '{ar_athan}' (Score={score_athan:.2f})",
                    level="INFO",
                )
                return athan_canonical

        # Return transcription as-is
        return txt

    # --- 1) Athan detection via dictionary ---
    # Check if we have a direct translation for the target language
    score_athan, athan_trans, ar_athan = fuzzy_match_athan(txt, target_lang_code)
    if score_athan >= ATHAN_MATCH_THRESHOLD and athan_trans:
        log(
            f"Athan detected: '{ar_athan}' → '{athan_trans}' (Score={score_athan:.2f})",
            level="INFO",
        )
        # If we have a direct translation for this language, return it
        if has_athan_translation(target_lang_code):
            return athan_trans
        # Otherwise, fall through to GPT for translation

    # --- 2) Quran detection via RAG (multiple matches) ---
    quran_matches = match_quran_rag_multi(txt, target_lang_code=target_lang_code)
    quran_hint = _build_quran_hint(quran_matches, target_lang)

    log(
        f"Quran-RAG hints generated with {len(quran_matches)} candidates.",
        level="DEBUG",
    )

    # --- 3) GPT Translation with model fallback ---
    system_prompt = _build_system_prompt(source_lang, target_lang)
    user_prompt = _build_user_prompt(txt, context, quran_hint, source_lang, target_lang)

    # Build fallback chain: primary model first, then fallbacks (deduplicated)
    primary_model = _get_translation_model()
    models_to_try = [primary_model]
    for fallback in FALLBACK_TRANSLATION_MODELS:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_error = None
    for model in models_to_try:
        try:
            log(f"Trying model: {model}", level="DEBUG")

            def _call_translation_api():
                return get_client().chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )

            resp = retry_with_backoff(
                _call_translation_api,
                max_retries=2,  # Fewer retries per model since we have fallbacks
                operation_name=f"Translation ({model})",
            )
            translation = resp.choices[0].message.content.strip()
            log(
                f"TRANSLATOR Final output ({target_lang}): {translation}", level="DEBUG"
            )
            return translation

        except Exception as e:
            last_error = e
            log(f"Model {model} failed: {e}", level="WARNING")
            continue  # Try next model

    # All models failed
    log(f"All translation models failed. Last error: {last_error}", level="ERROR")
    return "[⚠️ Übersetzung nicht verfügbar]"
