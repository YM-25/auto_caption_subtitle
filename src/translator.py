"""
Segment translation using deep_translator (Google Translate).
One translator instance is reused for all segments to avoid repeated setup.
"""

from deep_translator import GoogleTranslator


def apply_glossary(text, glossary):
    if not glossary:
        return text
    ordered = sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True)
    updated = text
    for src, tgt in ordered:
        if not src:
            continue
        updated = updated.replace(src, tgt)
    return updated


def translate_segments(segments, target_lang="en", progress_callback=None, glossary=None):
    """
    Translate segment texts to the target language; keep timings and 1:1 order for dual SRT.

    Args:
        segments: List of dicts with 'text', 'start', 'end' (from Whisper).
        target_lang: Target language code (e.g. 'en', 'zh-CN').

    Returns:
        List of segment dicts with 'text' replaced by translated text.
    """
    translated_segments = []
    effective_target = target_lang
    if target_lang in ("en-GB", "en-UK"):
        effective_target = "en"
        print(f"Target language '{target_lang}' not supported by translator. Using '{effective_target}' instead.")

    print(f"Translating {len(segments)} segments to '{effective_target}'...")

    translator = GoogleTranslator(source="auto", target=effective_target)

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
            translated_text = translator.translate(original_text)
            new_seg['text'] = apply_glossary(translated_text, glossary)
        except Exception as e:
            print(f"Failed to translate segment {i}: {e}")
            # Keep original text if translation fails

        translated_segments.append(new_seg)
        if progress_callback:
            progress_callback(i + 1, total)

    return translated_segments
