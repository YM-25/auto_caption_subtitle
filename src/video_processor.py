"""
Video processing utilities for audio extraction using ffmpeg.
"""

import shutil
import ffmpeg


class FFmpegNotFoundError(Exception):
    """Raised when ffmpeg is not available in the system."""
    pass


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def convert_video_to_audio(video_path: str, audio_output_path: str) -> None:
    """
    Converts a video file to audio using ffmpeg.

    Args:
        video_path: Path to the input video file.
        audio_output_path: Path to the output audio file.

    Raises:
        FFmpegNotFoundError: If ffmpeg is not installed or not in PATH.
        ffmpeg.Error: If the conversion fails.
    """
    if not check_ffmpeg_available():
        raise FFmpegNotFoundError(
            "ffmpeg is not installed or not found in PATH. "
            "Please install ffmpeg (https://ffmpeg.org/download.html) and ensure it is in your system PATH."
        )

    try:
        print(f"Converting '{video_path}' to '{audio_output_path}'...")
        (
            ffmpeg
            .input(video_path)
            .audio
            .output(audio_output_path)
            .overwrite_output()
            .run(quiet=True)
        )
        print(f"Successfully converted to '{audio_output_path}'")
    except ffmpeg.Error as e:
        print(f"Error converting video to audio: {e.stderr.decode() if e.stderr else str(e)}")
        raise
