import os
import glob
from .video_processor import convert_video_to_audio
from .transcriber import transcribe_audio, save_transcript, save_srt, save_dual_srt
from .translator import translate_segments

# Configuration
# Allow overriding base dir for flexibility
def get_paths(base_dir=None):
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return {
        'videos': os.path.join(base_dir, 'data', 'videos'),
        'audios': os.path.join(base_dir, 'data', 'audios'),
        'transcripts': os.path.join(base_dir, 'data', 'transcripts')
    }

def process_video(video_path, source_lang=None, target_lang=None, progress_callback=None):
    """
    Process a single video file: Convert -> Transcribe -> Translate (opt)
    
    Args:
        video_path (str): Absolute path to the video file.
        source_lang (str, optional): Source language code.
        target_lang (str, optional): Target language for translation.
        progress_callback (func, optional): Function to call with status updates (str).
    
    Returns:
        dict: Paths to generated files. 
        Keys: 'original', 'translated', 'dual'
    """
    def log(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    paths = get_paths()
    os.makedirs(paths['audios'], exist_ok=True)
    os.makedirs(paths['transcripts'], exist_ok=True)
    
    video_filename = os.path.basename(video_path)
    video_name_no_ext = os.path.splitext(video_filename)[0]
    
    # Define output paths
    audio_filename = f"{video_name_no_ext}.mp3"
    audio_path = os.path.join(paths['audios'], audio_filename)
    
    transcript_filename = f"{video_name_no_ext}.txt"
    transcript_path = os.path.join(paths['transcripts'], transcript_filename)
    
    # NEW NAMING CONVENTION: _ori.srt
    srt_filename = f"{video_name_no_ext}_ori.srt"
    srt_path = os.path.join(paths['transcripts'], srt_filename)

    output_files = {}

    log(f"Starting processing for {video_filename}...")

    # Step 1: Video to Audio
    log("Step 1/4: Converting video to audio...")
    if not os.path.exists(audio_path):
        try:
            convert_video_to_audio(video_path, audio_path)
            log("Audio conversion complete.")
        except Exception as e:
            log(f"Audio conversion failed: {e}")
            raise
    else:
        log("Audio file already exists, skipping conversion.")
    
    # Step 2: Audio to Text & Subtitles
    try:
        # Transcribe
        log(f"Step 2/4: Transcribing audio (Source: {source_lang or 'Auto'})...")
        result = transcribe_audio(audio_path, language=source_lang)
        text = result["text"]
        segments = result["segments"]
        detected_lang = result["language"]
        
        log(f"Transcription complete. Detected language: {detected_lang}")
        
        # Save plain text
        log("Saving transcripts...")
        save_transcript(text, transcript_path)
        
        # Save original SRT
        save_srt(segments, srt_path)
        output_files['original'] = srt_path
        
        # Step 3: Determine Target Language
        log("Step 3/4: Determining target language...")
        if target_lang is None or target_lang == 'auto':
            # Logic: If English -> Chinese, Else -> English
            # We treat 'en' from detection as English
            is_english = detected_lang.lower().startswith('en')
            target_lang = 'zh-CN' if is_english else 'en'
            log(f"Auto-selected target language: {target_lang}")
        else:
            log(f"Using requested target language: {target_lang}")
        
        # Step 4: Translation
        log(f"Step 4/4: Translating subtitles to '{target_lang}'...")
        
        # Only translate if target is different from source/detected
        if target_lang != detected_lang:
            
            translated_segments = translate_segments(segments, target_lang=target_lang)
            
            # NEW NAMING CONVENTION: _trans.srt
            translated_srt_filename = f"{video_name_no_ext}_trans.srt"
            translated_srt_path = os.path.join(paths['transcripts'], translated_srt_filename)
            
            save_srt(translated_segments, translated_srt_path)
            output_files['translated'] = translated_srt_path
            
            # Step 5: Dual Language (Bilingual)
            log("Generating dual-language subtitles...")
            
            # NEW NAMING CONVENTION: _dual.srt
            dual_srt_filename = f"{video_name_no_ext}_dual.srt"
            dual_srt_path = os.path.join(paths['transcripts'], dual_srt_filename)
            
            save_dual_srt(segments, translated_segments, dual_srt_path)
            output_files['dual'] = dual_srt_path
            
            log("Translation and dual-subs generation complete.")
        else:
            log("Target language matches source language. Skipping translation.")
        
        log("Processing finished successfully!")
        
    except Exception as e:
        log(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    return output_files

def main():
    # Legacy main for CLI usage
    pass

if __name__ == "__main__":
    main()
