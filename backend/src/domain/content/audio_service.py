from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.content.models import AudioAsset, Sentence, SentenceAudioAsset, Word, WordAudioAsset
from settings import get_settings

AUDIO_PROVIDER_ELEVENLABS = "elevenlabs"
AUDIO_STATUS_FAILED = "failed"
AUDIO_STATUS_READY = "ready"
LANGUAGE_CODE_JA = "ja"
MIME_TYPE_MP3 = "audio/mpeg"


@dataclass(frozen=True, slots=True)
class AudioAssetIdentity:
    provider: str
    voice_id: str
    model_id: str
    text_hash: str
    source_text: str


@dataclass(frozen=True, slots=True)
class SentenceAudioIdentity:
    sentence_id: str
    audio: AudioAssetIdentity

    @property
    def source_text(self) -> str:
        return self.audio.source_text


@dataclass(frozen=True, slots=True)
class WordAudioIdentity:
    word_id: str
    audio: AudioAssetIdentity

    @property
    def source_text(self) -> str:
        return self.audio.source_text


def audio_identity_from_text(*, text: str, provider: str, voice_id: str, model_id: str) -> AudioAssetIdentity:
    normalized_text = normalize_audio_text(text)
    return AudioAssetIdentity(
        provider=provider,
        voice_id=voice_id,
        model_id=model_id,
        text_hash=audio_text_digest(
            provider=provider,
            voice_id=voice_id,
            model_id=model_id,
            normalized_text=normalized_text,
        ),
        source_text=text,
    )


def sentence_audio_identity(*, sentence: Sentence, provider: str, voice_id: str, model_id: str) -> SentenceAudioIdentity:
    return SentenceAudioIdentity(
        sentence_id=sentence.id,
        audio=audio_identity_from_text(
            text=sentence.ja_text,
            provider=provider,
            voice_id=voice_id,
            model_id=model_id,
        ),
    )


def word_audio_identity(*, word: Word, provider: str, voice_id: str, model_id: str) -> WordAudioIdentity:
    return WordAudioIdentity(
        word_id=word.id,
        audio=audio_identity_from_text(
            text=word.reading_kana,
            provider=provider,
            voice_id=voice_id,
            model_id=model_id,
        ),
    )


def normalize_audio_text(text: str) -> str:
    return " ".join(text.split())


def audio_text_digest(*, provider: str, voice_id: str, model_id: str, normalized_text: str) -> str:
    return sha256(f"{provider}:{voice_id}:{model_id}:{normalized_text}".encode()).hexdigest()


def audio_asset_ready_on_disk(asset: AudioAsset | SentenceAudioAsset | WordAudioAsset) -> bool:
    return asset.status == AUDIO_STATUS_READY and Path(asset.storage_path).exists()


def get_audio_asset(db: Session, *, asset_id: str) -> AudioAsset | None:
    return db.get(AudioAsset, asset_id)


def get_audio_asset_by_identity(db: Session, *, identity: AudioAssetIdentity) -> AudioAsset | None:
    return db.scalar(
        select(AudioAsset).where(
            AudioAsset.provider == identity.provider,
            AudioAsset.voice_id == identity.voice_id,
            AudioAsset.model_id == identity.model_id,
            AudioAsset.text_hash == identity.text_hash,
        )
    )


def get_reusable_audio_asset(db: Session, *, identity: AudioAssetIdentity) -> AudioAsset | None:
    asset = db.scalar(
        select(AudioAsset)
        .where(
            AudioAsset.provider == identity.provider,
            AudioAsset.voice_id == identity.voice_id,
            AudioAsset.model_id == identity.model_id,
            AudioAsset.text_hash == identity.text_hash,
            AudioAsset.status == AUDIO_STATUS_READY,
        )
        .order_by(AudioAsset.created_at.desc(), AudioAsset.id.desc())
        .limit(1)
    )
    if asset is None or not audio_asset_ready_on_disk(asset):
        return None
    return asset


def create_or_update_audio_asset(
    db: Session,
    *,
    identity: AudioAssetIdentity,
    storage_path: Path,
    mime_type: str,
) -> AudioAsset:
    asset = get_audio_asset_by_identity(db, identity=identity)
    if asset is None:
        asset = AudioAsset(
            provider=identity.provider,
            voice_id=identity.voice_id,
            model_id=identity.model_id,
            language_code=LANGUAGE_CODE_JA,
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
    asset.source_text = identity.source_text
    asset.storage_path = str(storage_path)
    asset.mime_type = mime_type
    db.flush()
    return asset


def get_sentence_audio_asset(db: Session, *, asset_id: str) -> SentenceAudioAsset | None:
    return db.get(SentenceAudioAsset, asset_id)


def get_word_audio_asset(db: Session, *, asset_id: str) -> WordAudioAsset | None:
    return db.get(WordAudioAsset, asset_id)


def get_ready_sentence_audio_asset(
    db: Session,
    *,
    sentence_id: str,
    provider: str,
    voice_id: str,
    model_id: str,
) -> SentenceAudioAsset | None:
    asset = db.scalar(
        select(SentenceAudioAsset)
        .where(
            SentenceAudioAsset.sentence_id == sentence_id,
            SentenceAudioAsset.provider == provider,
            SentenceAudioAsset.voice_id == voice_id,
            SentenceAudioAsset.model_id == model_id,
            SentenceAudioAsset.status == AUDIO_STATUS_READY,
        )
        .order_by(SentenceAudioAsset.created_at.desc(), SentenceAudioAsset.id.desc())
        .limit(1)
    )
    if asset is None or not audio_asset_ready_on_disk(asset):
        return None
    return asset


def get_ready_word_audio_asset(
    db: Session,
    *,
    word_id: str,
    provider: str,
    voice_id: str,
    model_id: str,
) -> WordAudioAsset | None:
    asset = db.scalar(
        select(WordAudioAsset)
        .where(
            WordAudioAsset.word_id == word_id,
            WordAudioAsset.provider == provider,
            WordAudioAsset.voice_id == voice_id,
            WordAudioAsset.model_id == model_id,
            WordAudioAsset.status == AUDIO_STATUS_READY,
        )
        .order_by(WordAudioAsset.created_at.desc(), WordAudioAsset.id.desc())
        .limit(1)
    )
    if asset is None or not audio_asset_ready_on_disk(asset):
        return None
    return asset


def get_sentence_audio_asset_by_identity(db: Session, *, identity: SentenceAudioIdentity) -> SentenceAudioAsset | None:
    return db.scalar(
        select(SentenceAudioAsset).where(
            SentenceAudioAsset.sentence_id == identity.sentence_id,
            SentenceAudioAsset.provider == identity.audio.provider,
            SentenceAudioAsset.voice_id == identity.audio.voice_id,
            SentenceAudioAsset.model_id == identity.audio.model_id,
            SentenceAudioAsset.text_hash == identity.audio.text_hash,
        )
    )


def get_word_audio_asset_by_identity(db: Session, *, identity: WordAudioIdentity) -> WordAudioAsset | None:
    return db.scalar(
        select(WordAudioAsset).where(
            WordAudioAsset.word_id == identity.word_id,
            WordAudioAsset.provider == identity.audio.provider,
            WordAudioAsset.voice_id == identity.audio.voice_id,
            WordAudioAsset.model_id == identity.audio.model_id,
            WordAudioAsset.text_hash == identity.audio.text_hash,
        )
    )


def _sync_audio_projection_fields(
    *,
    storage_path: Path,
    mime_type: str,
    audio_asset_id: str,
    target: SentenceAudioAsset | WordAudioAsset,
) -> None:
    target.audio_asset_id = audio_asset_id
    target.storage_path = str(storage_path)
    target.mime_type = mime_type


def create_or_update_sentence_audio_asset(
    db: Session,
    *,
    identity: SentenceAudioIdentity,
    audio_asset: AudioAsset,
    storage_path: Path,
    mime_type: str,
) -> SentenceAudioAsset:
    asset = get_sentence_audio_asset_by_identity(db, identity=identity)
    if asset is None:
        asset = SentenceAudioAsset(
            audio_asset_id=audio_asset.id,
            sentence_id=identity.sentence_id,
            provider=identity.audio.provider,
            voice_id=identity.audio.voice_id,
            model_id=identity.audio.model_id,
            language_code=LANGUAGE_CODE_JA,
            text_hash=identity.audio.text_hash,
            source_text=identity.audio.source_text,
            storage_path=str(storage_path),
            mime_type=mime_type,
            byte_size=0,
            status=AUDIO_STATUS_FAILED,
        )
        db.add(asset)
        db.flush()
        return asset
    asset.source_text = identity.audio.source_text
    _sync_audio_projection_fields(storage_path=storage_path, mime_type=mime_type, audio_asset_id=audio_asset.id, target=asset)
    db.flush()
    return asset


def create_or_update_word_audio_asset(
    db: Session,
    *,
    identity: WordAudioIdentity,
    audio_asset: AudioAsset,
    storage_path: Path,
    mime_type: str,
) -> WordAudioAsset:
    asset = get_word_audio_asset_by_identity(db, identity=identity)
    if asset is None:
        asset = WordAudioAsset(
            audio_asset_id=audio_asset.id,
            word_id=identity.word_id,
            provider=identity.audio.provider,
            voice_id=identity.audio.voice_id,
            model_id=identity.audio.model_id,
            language_code=LANGUAGE_CODE_JA,
            text_hash=identity.audio.text_hash,
            source_text=identity.audio.source_text,
            storage_path=str(storage_path),
            mime_type=mime_type,
            byte_size=0,
            status=AUDIO_STATUS_FAILED,
        )
        db.add(asset)
        db.flush()
        return asset
    asset.source_text = identity.audio.source_text
    _sync_audio_projection_fields(storage_path=storage_path, mime_type=mime_type, audio_asset_id=audio_asset.id, target=asset)
    db.flush()
    return asset


def build_sentence_audio_url(*, asset_id: str) -> str:
    return f"/api/v1/sentence-audio/{asset_id}"


def build_word_audio_url(*, asset_id: str) -> str:
    return f"/api/v1/word-audio/{asset_id}"


def resolve_sentence_audio_url(db: Session, *, sentence_id: str | None) -> str | None:
    if sentence_id is None:
        return None
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        return None
    asset = get_ready_sentence_audio_asset(
        db,
        sentence_id=sentence_id,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    if asset is None:
        return None
    return build_sentence_audio_url(asset_id=asset.id)


def resolve_word_audio_url(db: Session, *, word_id: str | None) -> str | None:
    if word_id is None:
        return None
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        return None
    asset = get_ready_word_audio_asset(
        db,
        word_id=word_id,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    if asset is None:
        return None
    return build_word_audio_url(asset_id=asset.id)


def get_accessible_sentence_audio_asset_or_404(
    db: Session,
    *,
    asset_id: str,
    course_version_id: str,
) -> SentenceAudioAsset:
    asset = get_sentence_audio_asset(db, asset_id=asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence audio not found")
    sentence = db.get(Sentence, asset.sentence_id)
    if sentence is None or sentence.course_version_id != course_version_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence audio not found")
    if not audio_asset_ready_on_disk(asset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sentence audio not available")
    return asset


def get_accessible_word_audio_asset_or_404(
    db: Session,
    *,
    asset_id: str,
    course_version_id: str,
) -> WordAudioAsset:
    asset = get_word_audio_asset(db, asset_id=asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word audio not found")
    word = db.get(Word, asset.word_id)
    if word is None or word.course_version_id != course_version_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word audio not found")
    if not audio_asset_ready_on_disk(asset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word audio not available")
    return asset
