from __future__ import annotations

from collections.abc import Iterable

from elevenlabs.client import ElevenLabs

from settings import get_settings


class ElevenLabsSpeechClient:
    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.elevenlabs_api_key
        voice_id = settings.elevenlabs_voice_id
        if api_key is None or voice_id is None:
            msg = "ElevenLabs is not configured; both ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required"
            raise ValueError(msg)
        self._voice_id = voice_id
        self._model_id = settings.elevenlabs_model_id
        self._client = ElevenLabs(
            api_key=api_key.get_secret_value(),
            base_url=settings.elevenlabs_base_url,
        )

    @property
    def voice_id(self) -> str:
        return self._voice_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def synthesize(self, *, text: str) -> bytes:
        chunks = self._client.text_to_speech.convert(
            voice_id=self._voice_id,
            model_id=self._model_id,
            output_format="mp3_44100_128",
            language_code="ja",
            text=text,
            voice_settings={
                "speed": 0.78,
                "stability": 0.7,
                "similarity_boost": 0.8,
                "style": 0.0,
                "speaker_boost": True,
            },
        )
        return _collect_audio_bytes(chunks)


def _collect_audio_bytes(chunks: Iterable[bytes] | bytes) -> bytes:
    if isinstance(chunks, bytes):
        return chunks
    return b"".join(chunk for chunk in chunks if chunk)
