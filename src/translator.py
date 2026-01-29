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
    
    # Translate in batches or one by one. For simplicity and reliability, loop.
    for i, segment in enumerate(segments):
        original_text = segment['text'].strip()
        if not original_text:
            continue
            
        new_seg = segment.copy()
        try:
             # Progress log every 10 segments
            if i % 10 == 0:
                print(f"Translating segment {i}/{len(segments)}: {original_text[:20]}...")
            
            translated_text = translator.translate(original_text)
            new_seg['text'] = translated_text
        except Exception as e:
            print(f"Failed to translate segment {i}: {e}")
            # Keep original text if translation fails
            pass
            
        translated_segments.append(new_seg)
        
    return translated_segments
