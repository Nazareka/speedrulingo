from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.content.models import AudioAsset
from domain.kana.audio_service import ensure_kana_audio_asset, kana_tts_text
from domain.kana.catalog import ensure_kana_catalog_seeded
from domain.kana.models import KanaCharacter


class _FakeSpeechClient:
    voice_id = "voice-test"
    model_id = "model-test"

    def synthesize(self, *, text: str) -> bytes:
        return f"audio:{text}".encode()


def test_hiragana_and_katakana_reuse_shared_asset_with_extended_tts_prompt(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ensure_kana_catalog_seeded(db_session)
    monkeypatch.setattr("domain.kana.audio_service.ElevenLabsSpeechClient", _FakeSpeechClient)
    monkeypatch.setattr(
        "domain.kana.audio_service.get_settings",
        lambda: type("Settings", (), {"audio_storage_root": tmp_path / "audio", "elevenlabs_voice_id": "voice-test", "elevenlabs_model_id": "model-test"})(),
    )

    hiragana = db_session.scalar(select(KanaCharacter).where(KanaCharacter.char == "あ").limit(1))
    katakana = db_session.scalar(select(KanaCharacter).where(KanaCharacter.char == "ア").limit(1))
    assert hiragana is not None
    assert katakana is not None

    kana_asset, reused_existing = ensure_kana_audio_asset(db_session, character_id=hiragana.id)
    assert reused_existing is False
    assert kana_asset.source_text == "あー。"

    katakana_asset, reused_from_shared = ensure_kana_audio_asset(db_session, character_id=katakana.id)
    assert reused_from_shared is True
    assert katakana_asset.storage_path == kana_asset.storage_path
    assert katakana_asset.audio_asset_id == kana_asset.audio_asset_id

    shared_assets = list(
        db_session.scalars(select(AudioAsset).where(AudioAsset.text_hash == kana_asset.text_hash))
    )
    assert len(shared_assets) == 1


def test_kana_tts_text_adds_long_vowel_and_punctuation() -> None:
    assert kana_tts_text(sound_text="あ") == "あー。"
