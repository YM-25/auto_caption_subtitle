"""
Whisper transcription and SRT file generation utilities.
"""

import math
from typing import Dict, List, Optional

import torch
import whisper


def transcribe_audio(
    audio_path: str,
    model_name: str = "base",
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None,
) -> Dict:
    """
    Transcribe an audio file using OpenAI Whisper.

    Args:
        audio_path: Path to the input audio file.
        model_name: Whisper model (tiny, base, small, medium, large).
        language: Language code (e.g. 'en', 'zh'). None = auto-detect.
        initial_prompt: Optional prompt for names, places, jargon to bias transcription.

    Returns:
        dict: 'text', 'segments', 'language' (and other Whisper keys).
    """
    print(f"Loading Whisper model '{model_name}'...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model(model_name, device=device)

    print(f"Transcribing '{audio_path}' with language='{language}'...")

    options: Dict = {}
    if language and language != "auto":
        options["language"] = language
    if initial_prompt:
        options["initial_prompt"] = initial_prompt
    result = model.transcribe(audio_path, **options)

    return result


def format_timestamp(seconds: float) -> str:
    """Formats seconds into SRT timestamp format (HH:MM:SS,mmm)."""
    hours = math.floor(seconds / 3600)
    seconds %= 3600
    minutes = math.floor(seconds / 60)
    seconds %= 60
    milliseconds = round((seconds - math.floor(seconds)) * 1000)
    seconds = math.floor(seconds)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def save_srt(segments: List[Dict], output_path: str) -> None:
    """Saves segments to an SRT file."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip()

            f.write(f"{i + 1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")

    print(f"SRT saved to '{output_path}'")


def save_dual_srt(
    original_segments: List[Dict], translated_segments: List[Dict], output_path: str
) -> None:
    """
    Saves dual-language segments to an SRT file.

    Structure: Translated text on top, Original text on bottom.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for i, (orig, trans) in enumerate(zip(original_segments, translated_segments)):
            start = format_timestamp(orig["start"])
            end = format_timestamp(orig["end"])

            orig_text = orig["text"].strip()
            trans_text = trans["text"].strip()

            combined_text = f"{trans_text}\n{orig_text}"

            f.write(f"{i + 1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{combined_text}\n\n")

    print(f"Dual SRT saved to '{output_path}'")


def save_transcript(text: str, output_path: str) -> None:
    """Saves the transcribed text to a file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Transcript saved to '{output_path}'")
