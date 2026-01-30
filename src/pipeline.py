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


def process_video(video_path, source_lang=None, target_lang=None, model_name=None, progress_callback=None):
    """
    Process a single video: Convert → Transcribe → (optionally) Translate → SRT files.

    Args:
        video_path: Absolute path to the video file.
        source_lang: Source language code (e.g. 'en', 'zh'). None = auto-detect.
        target_lang: Target language for translation. None = transcript only;
            'auto' = smart select (English→Chinese, others→English).
        model_name: Whisper model override (e.g. 'small'); None uses default.
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
        def whisper_lang_from_ui(code):
            if not code:
                return None
            norm = normalize_lang_code(code)
            if norm.startswith("zh"):
                return "zh"
            if norm == "en":
                return "en"
            return code.split("-")[0] if "-" in code else code

        whisper_source = whisper_lang_from_ui(source_lang)

        active_model = model_name or WHISPER_MODEL
        log(f"Step 2/4: Transcribing audio (source: {source_lang or 'auto'}, model: {active_model})...")
        result = transcribe_audio(audio_path, model_name=active_model, language=whisper_source)
        text = result["text"]
        segments = result["segments"]
        detected_lang = result.get("language") or ""

        def auto_source_lang(code):
            if not code:
                return ""
            norm = normalize_lang_code(code)
            if norm in ("zh", "zh-cn"):
                return "zh-CN"
            if norm == "en":
                return "en-GB"
            return code

        def format_lang_tag(code):
            if not code:
                return "unknown"
            return code.strip().replace("_", "-").lower()

        def build_srt_name(base, src=None, tgt=None, dual=False):
            if src and tgt:
                name = f"{base}.{src}__{tgt}"
            elif src:
                name = f"{base}.{src}"
            else:
                name = base
            if dual:
                name = f"{name}.dual"
            return f"{name}.srt"

        effective_source = auto_source_lang(detected_lang) if source_lang is None else source_lang
        if source_lang is None and normalize_lang_code(detected_lang) == "zh" and normalize_lang_code(effective_source) == "zh-cn":
            log("Detected Chinese without script/region. Defaulting source to zh-CN (Simplified).")

        source_tag = format_lang_tag(effective_source or detected_lang)
        srt_path = os.path.join(paths["transcripts"], build_srt_name(video_name_no_ext, source_tag))

        log(f"Transcription complete. Detected language: {detected_lang}")
        if source_lang is None:
            log(f"Auto source language resolved to: {effective_source or detected_lang}")

        log("Saving transcripts...")
        save_transcript(text, transcript_path)
        save_srt(segments, srt_path)
        output_files["original"] = srt_path

        # Step 3: Target language
        log("Step 3/4: Determining target language...")
        if target_lang is None:
            effective_target = None
            do_dual = False
            log("Target language set to None (transcript only). Skipping translation.")
        elif target_lang == "auto":
            source_norm = normalize_lang_code(effective_source or detected_lang)
            if source_norm == "zh-cn":
                effective_target = "en-GB"
            elif source_norm == "en":
                effective_target = "zh-CN"
            else:
                effective_target = "en-GB"
            log(f"Auto-selected target language: {effective_target}")
            do_dual = True
        else:
            effective_target = target_lang
            do_dual = True

        # Step 4: Translate (only if target differs from source)
        if effective_target is None:
            log("Step 4/4: Translation skipped (transcript only).")
        else:
            log(f"Step 4/4: Translating subtitles to '{effective_target}'...")
        source_compare = normalize_lang_code(effective_source or detected_lang)
        if effective_target is not None and normalize_lang_code(effective_target) != source_compare:
            translated_segments = translate_segments(segments, target_lang=effective_target)
            target_tag = format_lang_tag(effective_target)
            translated_srt_path = os.path.join(
                paths["transcripts"],
                build_srt_name(video_name_no_ext, source_tag, target_tag),
            )
            save_srt(translated_segments, translated_srt_path)
            output_files["translated"] = translated_srt_path

            if do_dual:
                log("Generating dual-language subtitles...")
                dual_srt_path = os.path.join(
                    paths["transcripts"],
                    build_srt_name(video_name_no_ext, source_tag, target_tag, dual=True),
                )
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
