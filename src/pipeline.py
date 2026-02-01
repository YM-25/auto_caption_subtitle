"""
Video processing pipeline: convert → transcribe → translate → SRT output.

Uses src.config for paths and Whisper model name.
Language comparison uses normalized codes (e.g. zh-CN vs zh) to avoid ambiguity.
"""

import os

from .config import get_data_paths, normalize_lang_code, WHISPER_MODEL
from .video_processor import convert_video_to_audio
from .transcriber import transcribe_audio, save_transcript, save_srt, save_dual_srt
from .srt_utils import parse_srt_file, extract_source_segments, detect_language_from_text
from .translator import translate_segments
from .ai_service import expand_prompt


def _create_emit_fn(progress_callback):
    """Factory to create an emit function for progress reporting."""
    def emit(message, **payload):
        print(message)
        if progress_callback:
            data = {"type": "progress", "message": message}
            data.update(payload)
            progress_callback(data)
    return emit


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


def resolve_auto_target(source_code):
    source_norm = normalize_lang_code(source_code)
    if source_norm == "zh-cn":
        return "en-GB"
    if source_norm == "en":
        return "zh-CN"
    return "en-GB"


def convert_zh(text, segments, mode):
    try:
        from opencc import OpenCC
    except Exception:
        return text, segments, False

    converter = OpenCC(mode)
    new_text = converter.convert(text)
    new_segments = []
    for seg in segments:
        new_seg = seg.copy()
        new_seg["text"] = converter.convert(seg.get("text", ""))
        new_segments.append(new_seg)
    return new_text, new_segments, True


def process_video(video_path, source_lang=None, target_lang=None, model_name=None, initial_prompt=None, glossary=None, progress_callback=None, ai_options=None):
    """
    Process a single video: Convert → Transcribe → (optionally) Translate → SRT files.

    Args:
        video_path: Absolute path to the video file.
        source_lang: Source language code (e.g. 'en', 'zh'). None = auto-detect.
        target_lang: Target language for translation. None = transcript only;
            'auto' = smart select (English→Chinese, others→English).
        model_name: Whisper model override (e.g. 'small'); None uses default.
        initial_prompt: Optional prompt to bias Whisper transcription.
        glossary: Optional dict of term -> translation replacements.
        progress_callback: Optional callable(str) for status messages.

    Returns:
        dict: Paths to generated files. Keys: 'original', optionally 'translated', 'dual'.
    """
    emit = _create_emit_fn(progress_callback)

    paths = get_data_paths()
    os.makedirs(paths["audios"], exist_ok=True)
    os.makedirs(paths["transcripts"], exist_ok=True)


    video_filename = os.path.basename(video_path)
    video_name_no_ext = os.path.splitext(video_filename)[0]

    audio_path = os.path.join(paths["audios"], f"{video_name_no_ext}.mp3")
    transcript_path = os.path.join(paths["transcripts"], f"{video_name_no_ext}.txt")

    output_files = {}

    emit(f"Starting processing for {video_filename}...")

    # Step 1: Video → Audio
    emit("Step 1/4: Converting video to audio...", stage="prepare")
    if not os.path.exists(audio_path):
        try:
            convert_video_to_audio(video_path, audio_path)
            emit("Audio conversion complete.", stage="prepare")
        except Exception as e:
            emit(f"Audio conversion failed: {e}", stage="prepare")
            raise
    else:
        emit("Audio file already exists, skipping conversion.", stage="prepare")

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
        
        # Step 2a: AI Prompt Expansion
        if ai_options and ai_options.get("enable_expansion") and ai_options.get("api_key"):
            emit("Step 2/4: Expanding prompt using AI...", stage="transcribe")
            expanded = expand_prompt(
                video_filename, 
                user_prompt=initial_prompt, 
                provider=ai_options.get("provider", "gemini"), 
                api_key=ai_options.get("api_key"),
                model=ai_options.get("model"),
                glossary=glossary
            )
            if expanded:
                emit(f"AI expanded prompt: {expanded[:100]}...")
                initial_prompt = expanded

        prompt_note = "with prompt" if initial_prompt else "no prompt"
        emit(
            f"Step 2/4: Transcribing audio (source: {source_lang or 'auto'}, model: {active_model}, {prompt_note})...",
            stage="transcribe",
        )
        result = transcribe_audio(
            audio_path,
            model_name=active_model,
            language=whisper_source,
            initial_prompt=initial_prompt,
        )
        text = result["text"]
        segments = result["segments"]
        detected_lang = result.get("language") or ""
        emit(
            f"Transcription complete. {len(segments)} segments.",
            stage="transcribe",
            current=len(segments),
            total=len(segments),
            status="completed",
        )

        def auto_source_lang(code):
            if not code:
                return ""
            norm = normalize_lang_code(code)
            if norm in ("zh", "zh-cn"):
                return "zh-CN"
            if norm == "en":
                return "en-GB"
            return code

        effective_source = auto_source_lang(detected_lang) if source_lang is None else source_lang
        if source_lang is None and normalize_lang_code(detected_lang) == "zh" and normalize_lang_code(effective_source) == "zh-cn":
            emit("Detected Chinese without script/region. Defaulting source to zh-CN (Simplified).")

        # Step 2c: Chinese script conversion (OpenCC)
        # Normalize effective source to handle auto-detection accurately
        source_norm = normalize_lang_code(effective_source or detected_lang)
        
        conversion_mode = None
        if source_norm == "zh-cn":
            conversion_mode = "t2s"  # Traditional to Simplified
            msg = "Simplified Chinese (OpenCC t2s)"
        elif source_norm == "zh-tw":
            conversion_mode = "s2t"  # Simplified to Traditional
            msg = "Traditional Chinese (OpenCC s2t)"

        if conversion_mode:
            text, segments, converted = convert_zh(text, segments, conversion_mode)
            if converted:
                emit(f"Converted transcription to {msg}.", stage="transcribe")
            else:
                emit(f"OpenCC not installed. Skipping {msg} conversion.", stage="transcribe")

        source_tag = format_lang_tag(effective_source or detected_lang)
        srt_path = os.path.join(paths["transcripts"], build_srt_name(video_name_no_ext, source_tag))

        emit(f"Transcription complete. Detected language: {detected_lang}")
        if source_lang is None:
            emit(f"Auto source language resolved to: {effective_source or detected_lang}")

        emit("Saving transcripts...", stage="save")
        save_transcript(text, transcript_path)
        save_srt(segments, srt_path)
        output_files["original"] = srt_path

        # Step 3: Target language
        emit("Step 3/4: Determining target language...")
        if target_lang is None:
            effective_target = None
            do_dual = False
            emit("Target language set to None (transcript only). Skipping translation.")
        elif target_lang == "auto":
            effective_target = resolve_auto_target(effective_source or detected_lang)
            emit(f"Auto-selected target language: {effective_target}")
            do_dual = True
        else:
            effective_target = target_lang
            do_dual = True

        # Step 4: Translate (only if target differs from source)
        if effective_target is None:
            emit("Step 4/4: Translation skipped (transcript only).")
        else:
            emit(f"Step 4/4: Translating subtitles to '{effective_target}'...", stage="translate", current=0, total=len(segments))
        source_compare = normalize_lang_code(effective_source or detected_lang)
        if effective_target is not None and normalize_lang_code(effective_target) != source_compare:
            def on_translate_progress(current, total):
                emit(
                    f"Translating segments {current}/{total}...",
                    stage="translate",
                    current=current,
                    total=total,
                )

            translated_segments = translate_segments(
                segments,
                target_lang=effective_target,
                source_lang=effective_source or detected_lang,
                progress_callback=on_translate_progress,
                glossary=glossary,
                ai_options=ai_options,
            )
            target_tag = format_lang_tag(effective_target)
            translated_srt_path = os.path.join(
                paths["transcripts"],
                build_srt_name(video_name_no_ext, source_tag, target_tag),
            )
            save_srt(translated_segments, translated_srt_path)
            output_files["translated"] = translated_srt_path

            if do_dual:
                emit("Generating dual-language subtitles...", stage="save")
                dual_srt_path = os.path.join(
                    paths["transcripts"],
                    build_srt_name(video_name_no_ext, source_tag, target_tag, dual=True),
                )
                save_dual_srt(segments, translated_segments, dual_srt_path)
                output_files["dual"] = dual_srt_path
                emit("Translation and dual-subs generation complete.")
        else:
            emit("Target language matches source. Skipping translation.")

        emit("Processing finished successfully.")
    except Exception as e:
        emit(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    return output_files


def process_srt(srt_path, source_lang=None, target_lang="auto", glossary=None, progress_callback=None, ai_options=None):
    """
    Process an existing SRT file: Translate → SRT output.

    Args:
        srt_path: Absolute path to the input SRT file.
        source_lang: Source language code (e.g. 'en', 'zh-CN'). None/'auto' uses unknown.
        target_lang: Target language for translation. 'auto' = smart select;
            None skips translation.
        glossary: Optional dict of term -> translation replacements.
        progress_callback: Optional callable(str) for status messages.

    Returns:
        dict: Paths to generated files. Keys: 'original', 'translated', 'dual'.
    """
    emit = _create_emit_fn(progress_callback)

    paths = get_data_paths()
    os.makedirs(paths["transcripts"], exist_ok=True)

    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    if base_name.endswith(".uploaded"):
        base_name = base_name[: -len(".uploaded")]

    source_lang = None if source_lang in (None, "", "auto") else source_lang

    emit(f"Starting SRT translation for {os.path.basename(srt_path)}...")
    segments = parse_srt_file(srt_path)
    if not segments:
        raise ValueError("No subtitle segments found in SRT.")

    source_segments = extract_source_segments(segments, bilingual=True)

    if source_lang is None:
        combined_text = " ".join(seg["text"] for seg in source_segments if seg["text"]).strip()
        detected_source = detect_language_from_text(combined_text)
        source_lang = detected_source or ""

    source_tag = format_lang_tag(source_lang) if source_lang else "unknown"

    if target_lang is None:
        raise ValueError("Target language is required for SRT translation.")

    if target_lang == "auto":
        effective_target = resolve_auto_target(source_lang or "")
        emit(f"Auto-selected target language: {effective_target}")
    else:
        effective_target = target_lang

    emit(f"Translating SRT to '{effective_target}'...", stage="translate", current=0, total=len(source_segments))

    def on_translate_progress(current, total):
        emit(
            f"Translating segments {current}/{total}...",
            stage="translate",
            current=current,
            total=total,
        )

    translated_segments = translate_segments(
        source_segments,
        target_lang=effective_target,
        source_lang=source_lang,
        progress_callback=on_translate_progress,
        glossary=glossary,
        ai_options=ai_options,
    )

    target_tag = format_lang_tag(effective_target)
    original_srt_path = os.path.join(
        paths["transcripts"],
        build_srt_name(base_name, source_tag),
    )
    save_srt(source_segments, original_srt_path)

    translated_srt_path = os.path.join(
        paths["transcripts"],
        build_srt_name(base_name, source_tag, target_tag),
    )
    save_srt(translated_segments, translated_srt_path)

    dual_srt_path = os.path.join(
        paths["transcripts"],
        build_srt_name(base_name, source_tag, target_tag, dual=True),
    )
    save_dual_srt(source_segments, translated_segments, dual_srt_path)

    return {
        "original": original_srt_path,
        "translated": translated_srt_path,
        "dual": dual_srt_path,
    }
