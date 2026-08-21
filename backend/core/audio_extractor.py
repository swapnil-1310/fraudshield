import os
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

def extract_audio_from_video(video_path: str) -> Optional[str]:
    """
    Extract audio track from video file and save as .wav in config.TEMP_DIR.
    Uses ffmpeg command if available, otherwise returns None for video-only fallback.
    """
    if not os.path.exists(video_path):
        return None

    audio_filename = f"extracted_{Path(video_path).stem}.wav"
    output_audio_path = str(config.TEMP_DIR / audio_filename)

    # Try FFmpeg subprocess
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        cmd = [
            ffmpeg_exe, "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_audio_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if result.returncode == 0 and os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0:
            return output_audio_path
    except Exception as e:
        print(f"FFmpeg extraction note: {e}")

    return None
