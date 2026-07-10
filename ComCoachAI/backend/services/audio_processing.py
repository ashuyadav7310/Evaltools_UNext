# backend/services/audio_processing.py
import subprocess
import os
import sys

def get_ffmpeg_path():
    """Get ffmpeg executable path"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        # Fallback to system ffmpeg
        return "ffmpeg"

def convert_audio_to_wav(input_path: str, output_path: str) -> str:
    """
    Convert audio to WAV format
    """
    try:
        ffmpeg_exe = get_ffmpeg_path()
        
        cmd = [
            ffmpeg_exe,
            '-i', input_path,
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            '-y',
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return output_path
        
    except subprocess.CalledProcessError as e:
        raise Exception(f"Audio conversion failed: {e.stderr}")
    except Exception as e:
        raise Exception(f"Audio conversion failed: {str(e)}")

def validate_audio_file(file_path: str) -> bool:
    """
    Validate audio file exists and is readable
    """
    return os.path.exists(file_path) and os.path.getsize(file_path) > 0


def compress_audio_for_transcription(input_path: str, output_path: str = None, bitrate: str = "96k") -> str:  #compressor
    """
    Create a transcription-optimized compressed audio file (mono, 16kHz MP3).
    Keeps quality suitable for speech recognition while reducing file size.
    """
    try:  #compressor
        ffmpeg_exe = get_ffmpeg_path()  #compressor

        if output_path is None:  #compressor
            base_path, _ = os.path.splitext(input_path)  #compressor
            output_path = f"{base_path}.stt.mp3"  #compressor

        cmd = [  #compressor
            ffmpeg_exe,
            '-i', input_path,
            '-vn',  #compressor
            '-ac', '1',  #compressor
            '-ar', '16000',  #compressor
            '-b:a', bitrate,  #compressor
            '-codec:a', 'libmp3lame',  #compressor
            '-y',  #compressor
            output_path
        ]  #compressor

        subprocess.run(  #compressor
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        if not validate_audio_file(output_path):  #compressor
            raise Exception("Compressed audio file is invalid or empty")  #compressor

        return output_path  #compressor

    except subprocess.CalledProcessError as e:  #compressor
        raise Exception(f"Audio compression failed: {e.stderr}")  #compressor
    except Exception as e:  #compressor
        raise Exception(f"Audio compression failed: {str(e)}")  #compressor