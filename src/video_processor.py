import ffmpeg
import os

def convert_video_to_audio(video_path, audio_output_path):
    """
    Converts a video file to audio using ffmpeg.
    
    Args:
        video_path (str): Path to the input video file.
        audio_output_path (str): Path to the output audio file.
    """
    try:
        print(f"Converting '{video_path}' to '{audio_output_path}'...")
        # Overwrite output if exists (-y), input is video_path
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
        print(f"Error converting video to audio: {e}")
        raise
