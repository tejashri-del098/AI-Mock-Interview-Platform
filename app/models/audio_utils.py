import os
import asyncio
import whisper
import edge_tts
from typing import Optional

# Directory to store generated and recorded audio files
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

class WhisperManager:
    """Singleton manager for the local Whisper speech-to-text model to avoid loading latency."""
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            # We use 'tiny' by default for speed on CPU/MPS
            print("Loading Whisper model into memory...")
            cls._model = whisper.load_model("tiny")
        return cls._model

    @classmethod
    def transcribe(cls, file_path: str) -> str:
        """Transcribe an audio file to text. Returns empty string on silence/error."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found at {file_path}")
            
        # Check if file is essentially empty (less than 100 bytes)
        if os.path.getsize(file_path) < 100:
            return ""
            
        try:
            model = cls.get_model()
            result = model.transcribe(file_path)
            transcript = result.get("text", "").strip()
            return transcript
        except Exception as e:
            print(f"Whisper transcription error: {str(e)}")
            return ""


async def text_to_speech(text: str, filename: str, voice: str = "en-US-BrianNeural") -> str:
    """Convert text to speech asynchronously using edge-tts. Returns the absolute file path to the generated audio."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    output_path = os.path.join(AUDIO_DIR, filename)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path
