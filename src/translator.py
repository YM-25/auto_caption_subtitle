from deep_translator import GoogleTranslator

def translate_segments(segments, target_lang='en'):
    """
    Translates a list of segments to the target language.
    
    Args:
        segments (list): List of segment dictionaries (from Whisper).
        target_lang (str): Target language code (e.g., 'en', 'zh-CN').
        
    Returns:
        list: List of segments with translated text.
    """
    translated_segments = []
    print(f"Translating {len(segments)} segments to '{target_lang}'...")
    
    translator = GoogleTranslator(source='auto', target=target_lang)
    
    # Translate in batches or one by one. Keep 1:1 mapping for dual SRT.
    for i, segment in enumerate(segments):
        original_text = segment['text'].strip()
        new_seg = segment.copy()

        if not original_text:
            # Keep empty segment so dual SRT stays in sync
            translated_segments.append(new_seg)
            continue

        try:
            if i % 10 == 0:
                print(f"Translating segment {i}/{len(segments)}: {original_text[:20]}...")
            translated_text = translator.translate(original_text)
            new_seg['text'] = translated_text
        except Exception as e:
            print(f"Failed to translate segment {i}: {e}")
            # Keep original text if translation fails

        translated_segments.append(new_seg)

    return translated_segments
