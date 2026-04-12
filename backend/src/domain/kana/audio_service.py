from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.integrations.elevenlabs_client import ElevenLabsSpeechClient
from domain.content.audio_service import (
    AUDIO_PROVIDER_ELEVENLABS,
    AUDIO_STATUS_FAILED,
    AUDIO_STATUS_READY,
    MIME_TYPE_MP3,
    AudioAssetIdentity,
    audio_identity_from_text,
    create_or_update_audio_asset,
    get_reusable_audio_asset,
)
from domain.content.models import AudioAsset
from domain.kana.catalog import ensure_kana_catalog_seeded
from domain.kana.models import KanaAudioAsset, KanaCharacter
from settings import get_settings

_LONG_VOWEL_SOUNDS = frozenset({"あ", "い", "う", "え", "お"})


def kana_tts_text(*, sound_text: str) -> str:
    if sound_text in _LONG_VOWEL_SOUNDS:
        return f"{sound_text}ー。"
    return f"{sound_text}。"


def _kana_asset_ready_on_disk(asset: KanaAudioAsset) -> bool:
    return asset.status == AUDIO_STATUS_READY and Path(asset.storage_path).exists()


def build_kana_audio_url(*, asset_id: str) -> str:
    return f"/api/v1/kana/audio/{asset_id}"


def get_kana_audio_asset(db: Session, *, asset_id: str) -> KanaAudioAsset | None:
    return db.get(KanaAudioAsset, asset_id)


def get_kana_audio_asset_by_identity(db: Session, *, character_id: str, identity: AudioAssetIdentity) -> KanaAudioAsset | None:
    return db.scalar(
        select(KanaAudioAsset).where(
            KanaAudioAsset.character_id == character_id,
            KanaAudioAsset.provider == identity.provider,
            KanaAudioAsset.voice_id == identity.voice_id,
            KanaAudioAsset.model_id == identity.model_id,
            KanaAudioAsset.text_hash == identity.text_hash,
        )
    )


def create_or_update_kana_audio_asset(
    db: Session,
    *,
    character_id: str,
    identity: AudioAssetIdentity,
    audio_asset: AudioAsset,
    storage_path: Path,
    mime_type: str,
) -> KanaAudioAsset:
    asset = get_kana_audio_asset_by_identity(db, character_id=character_id, identity=identity)
    if asset is None:
        asset = KanaAudioAsset(
            audio_asset_id=audio_asset.id,
            character_id=character_id,
            provider=identity.provider,
            voice_id=identity.voice_id,
            model_id=identity.model_id,
            language_code="ja",
            text_hash=identity.text_hash,
            source_text=identity.source_text,
            storage_path=str(storage_path),
            mime_type=mime_type,
            byte_size=0,
            status=AUDIO_STATUS_FAILED,
        )
        db.add(asset)
        db.flush()
        return asset
    asset.audio_asset_id = audio_asset.id
    asset.source_text = identity.source_text
    asset.storage_path = str(storage_path)
    asset.mime_type = mime_type
    db.flush()
    return asset


def get_ready_kana_audio_asset(
    db: Session,
    *,
    character_id: str,
    provider: str,
    voice_id: str,
    model_id: str,
) -> KanaAudioAsset | None:
    asset = db.scalar(
        select(KanaAudioAsset)
        .where(
            KanaAudioAsset.character_id == character_id,
            KanaAudioAsset.provider == provider,
            KanaAudioAsset.voice_id == voice_id,
            KanaAudioAsset.model_id == model_id,
            KanaAudioAsset.status == AUDIO_STATUS_READY,
        )
        .order_by(KanaAudioAsset.created_at.desc(), KanaAudioAsset.id.desc())
        .limit(1)
    )
    if asset is None or not _kana_asset_ready_on_disk(asset):
        return None
    return asset


def resolve_kana_audio_url(db: Session, *, character_id: str) -> str | None:
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        return None
    asset = get_ready_kana_audio_asset(
        db,
        character_id=character_id,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    if asset is None:
        return None
    return build_kana_audio_url(asset_id=asset.id)


def _audio_path(*, identity: AudioAssetIdentity) -> Path:
    root = get_settings().audio_storage_root
    return root / identity.provider / identity.voice_id / f"{identity.text_hash}.mp3"


def _write_audio_bytes(*, storage_path: Path, payload: bytes) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = storage_path.with_suffix(f"{storage_path.suffix}.tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(storage_path)


def ensure_kana_audio_asset(db: Session, *, character_id: str) -> tuple[KanaAudioAsset, bool]:
    ensure_kana_catalog_seeded(db)
    character = db.get(KanaCharacter, character_id)
    if character is None:
        msg = f"Unknown character_id={character_id}"
        raise ValueError(msg)
    client = ElevenLabsSpeechClient()
    identity = audio_identity_from_text(
        text=kana_tts_text(sound_text=character.sound_text),
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=client.voice_id,
        model_id=client.model_id,
    )
    existing = get_kana_audio_asset_by_identity(db, character_id=character_id, identity=identity)
    if existing is not None and _kana_asset_ready_on_disk(existing):
        return existing, True

    shared_asset = get_reusable_audio_asset(db, identity=identity)
    if shared_asset is not None:
        asset = create_or_update_kana_audio_asset(
            db,
            character_id=character_id,
            identity=identity,
            audio_asset=shared_asset,
            storage_path=Path(shared_asset.storage_path),
            mime_type=shared_asset.mime_type,
        )
        asset.byte_size = shared_asset.byte_size
        asset.status = AUDIO_STATUS_READY
        asset.generation_error = None
        db.flush()
        return asset, True

    storage_path = _audio_path(identity=identity)
    shared_asset = create_or_update_audio_asset(db, identity=identity, storage_path=storage_path, mime_type=MIME_TYPE_MP3)
    audio_bytes = client.synthesize(text=identity.source_text)
    _write_audio_bytes(storage_path=storage_path, payload=audio_bytes)
    shared_asset.byte_size = len(audio_bytes)
    shared_asset.status = AUDIO_STATUS_READY
    shared_asset.generation_error = None
    asset = create_or_update_kana_audio_asset(
        db,
        character_id=character_id,
        identity=identity,
        audio_asset=shared_asset,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset.byte_size = len(audio_bytes)
    asset.status = AUDIO_STATUS_READY
    asset.generation_error = None
    db.flush()
    return asset, False


def mark_kana_audio_asset_failed(db: Session, *, character_id: str, error_message: str) -> None:
    character = db.get(KanaCharacter, character_id)
    if character is None:
        return
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        return
    identity = audio_identity_from_text(
        text=kana_tts_text(sound_text=character.sound_text),
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    storage_path = _audio_path(identity=identity)
    shared_asset = create_or_update_audio_asset(db, identity=identity, storage_path=storage_path, mime_type=MIME_TYPE_MP3)
    shared_asset.status = AUDIO_STATUS_FAILED
    shared_asset.generation_error = error_message
    asset = create_or_update_kana_audio_asset(
        db,
        character_id=character_id,
        identity=identity,
        audio_asset=shared_asset,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset.status = AUDIO_STATUS_FAILED
    asset.generation_error = error_message
    db.flush()


def get_accessible_kana_audio_asset_or_404(db: Session, *, asset_id: str) -> KanaAudioAsset:
    asset = get_kana_audio_asset(db, asset_id=asset_id)
    if asset is None or not _kana_asset_ready_on_disk(asset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kana audio not available")
    return asset


def backfill_kana_audio_assets(db: Session, *, script: str | None = None) -> list[str]:
    character_ids = list_kana_character_ids(db, script=script)
    for character_id in character_ids:
        ensure_kana_audio_asset(db, character_id=character_id)
    return character_ids


def list_kana_character_ids(db: Session, *, script: str | None = None) -> list[str]:
    ensure_kana_catalog_seeded(db)
    stmt = select(KanaCharacter.id).order_by(KanaCharacter.difficulty_rank.asc())
    if script is not None:
        stmt = stmt.where(KanaCharacter.script == script)
    return list(db.scalars(stmt))
