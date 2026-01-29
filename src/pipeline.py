"""
Video processing pipeline: convert → transcribe → translate → SRT output.

Uses src.config for paths and Whisper model name.
Language comparison uses normalized codes (e.g. zh-CN vs zh) to avoid ambiguity.
"""

import os

from .config import get_data_paths, normalize_lang_code, WHISPER_MODEL
from .video_processor import convert_video_to_audio
from .transcriber import transcribe_audio, save_transcript, save_srt, save_dual_srt
from .translator import translate_segments


def process_video(video_path, source_lang=None, target_lang=None, progress_callback=None):
    """
    Process a single video: Convert → Transcribe → (optionally) Translate → SRT files.

    Args:
        video_path: Absolute path to the video file.
        source_lang: Source language code (e.g. 'en', 'zh'). None = auto-detect.
        target_lang: Target language for translation. None = transcript only;
            'auto' = smart select (English→Chinese, others→English).
        progress_callback: Optional callable(str) for status messages.

    Returns:
        dict: Paths to generated files. Keys: 'original', optionally 'translated', 'dual'.
    """
    def log(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    paths = get_data_paths()
    os.makedirs(paths["audios"], exist_ok=True)
    os.makedirs(paths["transcripts"], exist_ok=True)

    video_filename = os.path.basename(video_path)
    video_name_no_ext = os.path.splitext(video_filename)[0]

    audio_path = os.path.join(paths["audios"], f"{video_name_no_ext}.mp3")
    transcript_path = os.path.join(paths["transcripts"], f"{video_name_no_ext}.txt")
    srt_path = os.path.join(paths["transcripts"], f"{video_name_no_ext}_ori.srt")

    output_files = {}

    log(f"Starting processing for {video_filename}...")

    # Step 1: Video → Audio
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

    try:
        # Step 2: Transcribe
        log(f"Step 2/4: Transcribing audio (source: {source_lang or 'auto'})...")
        result = transcribe_audio(audio_path, model_name=WHISPER_MODEL, language=source_lang)
        text = result["text"]
        segments = result["segments"]
        detected_lang = result.get("language") or ""

        log(f"Transcription complete. Detected language: {detected_lang}")

        log("Saving transcripts...")
        save_transcript(text, transcript_path)
        save_srt(segments, srt_path)
        output_files["original"] = srt_path

        # Step 3: Target language
        log("Step 3/4: Determining target language...")
        if target_lang is None or target_lang == "auto":
            is_english = normalize_lang_code(detected_lang) == "en"
            effective_target = "zh-CN" if is_english else "en"
            log(f"Auto-selected target language: {effective_target}")
            do_dual = True
        else:
            effective_target = target_lang
            do_dual = True

        # Step 4: Translate (only if target differs from source)
        log(f"Step 4/4: Translating subtitles to '{effective_target}'...")
        if normalize_lang_code(effective_target) != normalize_lang_code(detected_lang):
            translated_segments = translate_segments(segments, target_lang=effective_target)
            translated_srt_path = os.path.join(paths["transcripts"], f"{video_name_no_ext}_trans.srt")
            save_srt(translated_segments, translated_srt_path)
            output_files["translated"] = translated_srt_path

            if do_dual:
                log("Generating dual-language subtitles...")
                dual_srt_path = os.path.join(paths["transcripts"], f"{video_name_no_ext}_dual.srt")
                save_dual_srt(segments, translated_segments, dual_srt_path)
                output_files["dual"] = dual_srt_path
                log("Translation and dual-subs generation complete.")
        else:
            log("Target language matches source. Skipping translation.")

        log("Processing finished successfully.")
    except Exception as e:
        log(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    return output_files
