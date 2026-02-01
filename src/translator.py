"""
Segment translation using deep_translator (Google Translate).
One translator instance is reused for all segments to avoid repeated setup.
"""

from deep_translator import GoogleTranslator
from .ai_service import ai_translate_text


import re


def apply_glossary(text, glossary):
    if not glossary:
        return text

    # Sort by length descending to match longer phrases first
    ordered = sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True)
    updated = text

    for src, tgt in ordered:
        if not src:
            continue

        # If source term contains only word characters (Latin/Cyrillic/etc.), use word boundaries.
        # Otherwise (CJK or mixed), use literal replacement.
        if src.isalnum():
            # Use regex for word boundaries to avoid replacing parts of other words (e.g. 'cat' in 'category')
            pattern = rf"\b{re.escape(src)}\b"
            updated = re.sub(pattern, tgt, updated, flags=re.IGNORECASE if src.islower() else 0)
        else:
            # For CJK or mixed, literal replacement is safer and expected behavior
            updated = updated.replace(src, tgt)

    return updated


def _try_translate(translator, text):
    try:
        return translator.translate(text), None
    except Exception as e:
        return None, e


def translate_segments(
    segments,
    target_lang="en",
    source_lang="auto",
    progress_callback=None,
    glossary=None,
    ai_options=None,
):
    """
    Translate segment texts to the target language; keep timings and 1:1 order for dual SRT.

    Args:
        segments: List of dicts with 'text', 'start', 'end' (from Whisper).
        target_lang: Target language code (e.g. 'en', 'zh-CN').
        source_lang: Source language code (e.g. 'en', 'zh-TW', 'auto').
    """
    translated_segments = []
    effective_target = target_lang
    if target_lang in ("en-GB", "en-UK"):
        effective_target = "en"
        print(f"Target language '{target_lang}' not supported by translator. Using '{effective_target}' instead.")

    # Normalize source language for GoogleTranslator
    effective_source = source_lang or "auto"
    if effective_source.startswith("zh"):
        # Google Translator uses 'zh-CN' and 'zh-TW'. Our codes usually match.
        pass
    
    print(f"Translating {len(segments)} segments from '{effective_source}' to '{effective_target}'...")

    translator = GoogleTranslator(source=effective_source, target=effective_target)
    if ai_options and ai_options.get("enable_translation") and ai_options.get("api_key"):
        provider = ai_options.get("provider", "gemini")
        model = ai_options.get("model") or "default"
        print(f"Translation engine: AI ({provider}, model={model})")
    else:
        print("Translation engine: GoogleTranslator (deep_translator)")

    # One-by-one to preserve 1:1 mapping for dual SRT; empty segments kept as-is.
    total = len(segments)
    for i, segment in enumerate(segments):
        original_text = segment['text'].strip()
        new_seg = segment.copy()

        if not original_text:
            # Keep empty segment so dual SRT stays in sync
            translated_segments.append(new_seg)
            if progress_callback:
                progress_callback(i + 1, total)
            continue

        try:
            if i % 10 == 0:
                print(f"Translating segment {i}/{len(segments)}: {original_text[:20]}...")

            translated_text = None
            if ai_options and ai_options.get("enable_translation") and ai_options.get("api_key"):
                translated_text = ai_translate_text(
                    original_text,
                    target_lang=effective_target,
                    provider=ai_options.get("provider", "gemini"),
                    api_key=ai_options.get("api_key"),
                    model=ai_options.get("model"),
                    glossary=glossary,
                )

            # Fallback to Google Translate if AI is disabled or fails
            if translated_text is None:
                translated_text, google_error = _try_translate(translator, original_text)
                if google_error:
                    print(f"Failed to translate segment {i} via Google: {google_error}")

            if translated_text is not None:
                new_seg['text'] = apply_glossary(translated_text, glossary)
        except Exception as e:
            print(f"Failed to translate segment {i}: {e}")
            # Keep original text if translation fails

        translated_segments.append(new_seg)
        if progress_callback:
            progress_callback(i + 1, total)

    return translated_segments
