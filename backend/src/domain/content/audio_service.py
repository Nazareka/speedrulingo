from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from course_builder.elevenlabs import ElevenLabsSpeechClient
from domain.content.models import (
    Lesson,
    LessonSentence,
    LessonWord,
    Section,
    Sentence,
    SentenceAudioAsset,
    SentenceWordLink,
    Unit,
    Word,
    WordAudioAsset,
)
from settings import get_settings

AUDIO_PROVIDER_ELEVENLABS = "elevenlabs"
AUDIO_STATUS_FAILED = "failed"
AUDIO_STATUS_READY = "ready"
LANGUAGE_CODE_JA = "ja"
MIME_TYPE_MP3 = "audio/mpeg"


@dataclass(frozen=True, slots=True)
class SentenceAudioIdentity:
    sentence_id: str
    provider: str
    voice_id: str
    model_id: str
    text_hash: str
    source_text: str


@dataclass(frozen=True, slots=True)
class WordAudioIdentity:
    word_id: str
    provider: str
    voice_id: str
    model_id: str
    text_hash: str
    source_text: str


def sentence_audio_identity(*, sentence: Sentence, provider: str, voice_id: str, model_id: str) -> SentenceAudioIdentity:
    normalized_text = _normalize_audio_text(sentence.ja_text)
    digest = _audio_text_digest(
        provider=provider,
        voice_id=voice_id,
        model_id=model_id,
        normalized_text=normalized_text,
    )
    return SentenceAudioIdentity(
        sentence_id=sentence.id,
        provider=provider,
        voice_id=voice_id,
        model_id=model_id,
        text_hash=digest,
        source_text=sentence.ja_text,
    )


def word_audio_identity(*, word: Word, provider: str, voice_id: str, model_id: str) -> WordAudioIdentity:
    normalized_text = _normalize_audio_text(word.reading_kana)
    digest = _audio_text_digest(
        provider=provider,
        voice_id=voice_id,
        model_id=model_id,
        normalized_text=normalized_text,
    )
    return WordAudioIdentity(
        word_id=word.id,
        provider=provider,
        voice_id=voice_id,
        model_id=model_id,
        text_hash=digest,
        source_text=word.reading_kana,
    )


def list_section_sentence_ids(
    db: Session,
    *,
    course_version_id: str,
    section_code: str,
) -> list[str]:
    rows = db.execute(
        select(LessonSentence.sentence_id)
        .join(Lesson, Lesson.id == LessonSentence.lesson_id)
        .join(Unit, Unit.id == Lesson.unit_id)
        .join(Section, Section.id == Unit.section_id)
        .where(
            Section.course_version_id == course_version_id,
            Section.code == section_code,
        )
        .order_by(Section.order_index, Unit.order_index, Lesson.order_index, LessonSentence.order_index)
    ).all()
    ordered_sentence_ids = [row.sentence_id for row in rows]
    return list(dict.fromkeys(ordered_sentence_ids))


def list_section_word_ids(
    db: Session,
    *,
    course_version_id: str,
    section_code: str,
) -> list[str]:
    lesson_word_lesson = Lesson.__table__.alias("lesson_word_lesson")
    lesson_word_unit = Unit.__table__.alias("lesson_word_unit")
    sentence_lesson = Lesson.__table__.alias("sentence_lesson")
    sentence_unit = Unit.__table__.alias("sentence_unit")

    rows = db.execute(
        select(Word.id)
        .outerjoin(LessonWord, LessonWord.word_id == Word.id)
        .outerjoin(lesson_word_lesson, lesson_word_lesson.c.id == LessonWord.lesson_id)
        .outerjoin(lesson_word_unit, lesson_word_unit.c.id == lesson_word_lesson.c.unit_id)
        .outerjoin(SentenceWordLink, SentenceWordLink.word_id == Word.id)
        .outerjoin(LessonSentence, LessonSentence.sentence_id == SentenceWordLink.sentence_id)
        .outerjoin(sentence_lesson, sentence_lesson.c.id == LessonSentence.lesson_id)
        .outerjoin(sentence_unit, sentence_unit.c.id == sentence_lesson.c.unit_id)
        .join(
            Section,
            or_(
                Section.id == lesson_word_unit.c.section_id,
                Section.id == sentence_unit.c.section_id,
            ),
        )
        .where(
            Word.course_version_id == course_version_id,
            Section.code == section_code,
            Section.course_version_id == course_version_id,
        )
        .order_by(
            Section.order_index.asc(),
            lesson_word_unit.c.order_index.asc(),
            lesson_word_lesson.c.order_index.asc(),
            sentence_unit.c.order_index.asc(),
            sentence_lesson.c.order_index.asc(),
            Word.intro_order.asc(),
            Word.canonical_writing_ja.asc(),
            Word.id.asc(),
        )
    ).all()
    ordered_word_ids = [row.id for row in rows]
    return list(dict.fromkeys(ordered_word_ids))


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
    if asset is None:
        return None
    if not _asset_file_exists(asset):
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
    if asset is None:
        return None
    if not _asset_file_exists(asset):
        return None
    return asset


def get_sentence_audio_asset_by_identity(db: Session, *, identity: SentenceAudioIdentity) -> SentenceAudioAsset | None:
    return db.scalar(
        select(SentenceAudioAsset).where(
            SentenceAudioAsset.sentence_id == identity.sentence_id,
            SentenceAudioAsset.provider == identity.provider,
            SentenceAudioAsset.voice_id == identity.voice_id,
            SentenceAudioAsset.model_id == identity.model_id,
            SentenceAudioAsset.text_hash == identity.text_hash,
        )
    )


def get_reusable_sentence_audio_asset(
    db: Session, *, identity: SentenceAudioIdentity
) -> SentenceAudioAsset | None:
    asset = db.scalar(
        select(SentenceAudioAsset)
        .where(
            SentenceAudioAsset.provider == identity.provider,
            SentenceAudioAsset.voice_id == identity.voice_id,
            SentenceAudioAsset.model_id == identity.model_id,
            SentenceAudioAsset.text_hash == identity.text_hash,
            SentenceAudioAsset.status == AUDIO_STATUS_READY,
        )
        .order_by(SentenceAudioAsset.created_at.desc(), SentenceAudioAsset.id.desc())
        .limit(1)
    )
    if asset is None or not _asset_file_exists(asset):
        return None
    return asset


def get_word_audio_asset_by_identity(db: Session, *, identity: WordAudioIdentity) -> WordAudioAsset | None:
    return db.scalar(
        select(WordAudioAsset).where(
            WordAudioAsset.word_id == identity.word_id,
            WordAudioAsset.provider == identity.provider,
            WordAudioAsset.voice_id == identity.voice_id,
            WordAudioAsset.model_id == identity.model_id,
            WordAudioAsset.text_hash == identity.text_hash,
        )
    )


def get_reusable_word_audio_asset(db: Session, *, identity: WordAudioIdentity) -> WordAudioAsset | None:
    asset = db.scalar(
        select(WordAudioAsset)
        .where(
            WordAudioAsset.provider == identity.provider,
            WordAudioAsset.voice_id == identity.voice_id,
            WordAudioAsset.model_id == identity.model_id,
            WordAudioAsset.text_hash == identity.text_hash,
            WordAudioAsset.status == AUDIO_STATUS_READY,
        )
        .order_by(WordAudioAsset.created_at.desc(), WordAudioAsset.id.desc())
        .limit(1)
    )
    if asset is None or not _asset_file_exists(asset):
        return None
    return asset


def create_or_update_sentence_audio_asset(
    db: Session,
    *,
    identity: SentenceAudioIdentity,
    storage_path: Path,
    mime_type: str,
) -> SentenceAudioAsset:
    asset = get_sentence_audio_asset_by_identity(db, identity=identity)
    if asset is None:
        asset = SentenceAudioAsset(
            sentence_id=identity.sentence_id,
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


def create_or_update_word_audio_asset(
    db: Session,
    *,
    identity: WordAudioIdentity,
    storage_path: Path,
    mime_type: str,
) -> WordAudioAsset:
    asset = get_word_audio_asset_by_identity(db, identity=identity)
    if asset is None:
        asset = WordAudioAsset(
            word_id=identity.word_id,
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


def ensure_sentence_audio_asset(
    db: Session,
    *,
    sentence_id: str,
) -> tuple[SentenceAudioAsset, bool]:
    sentence = db.get(Sentence, sentence_id)
    if sentence is None:
        msg = f"Unknown sentence_id={sentence_id}"
        raise ValueError(msg)
    client = ElevenLabsSpeechClient()
    identity = sentence_audio_identity(
        sentence=sentence,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=client.voice_id,
        model_id=client.model_id,
    )
    existing_asset = get_sentence_audio_asset_by_identity(db, identity=identity)
    if existing_asset is not None and _asset_file_exists(existing_asset):
        return existing_asset, True

    reusable_asset = get_reusable_sentence_audio_asset(db, identity=identity)
    if reusable_asset is not None:
        asset = create_or_update_sentence_audio_asset(
            db,
            identity=identity,
            storage_path=Path(reusable_asset.storage_path),
            mime_type=reusable_asset.mime_type,
        )
        asset.byte_size = reusable_asset.byte_size
        asset.status = AUDIO_STATUS_READY
        asset.generation_error = None
        db.flush()
        return asset, True

    storage_path = _sentence_audio_path(identity=identity)
    asset = create_or_update_sentence_audio_asset(
        db,
        identity=identity,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    audio_bytes = client.synthesize(text=identity.source_text)
    _write_audio_bytes(storage_path=storage_path, payload=audio_bytes)
    asset.byte_size = len(audio_bytes)
    asset.status = AUDIO_STATUS_READY
    asset.generation_error = None
    db.flush()
    return asset, False


def ensure_word_audio_asset(
    db: Session,
    *,
    word_id: str,
) -> tuple[WordAudioAsset, bool]:
    word = db.get(Word, word_id)
    if word is None:
        msg = f"Unknown word_id={word_id}"
        raise ValueError(msg)
    client = ElevenLabsSpeechClient()
    identity = word_audio_identity(
        word=word,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=client.voice_id,
        model_id=client.model_id,
    )
    existing_asset = get_word_audio_asset_by_identity(db, identity=identity)
    if existing_asset is not None and _asset_file_exists(existing_asset):
        return existing_asset, True

    reusable_asset = get_reusable_word_audio_asset(db, identity=identity)
    if reusable_asset is not None:
        asset = create_or_update_word_audio_asset(
            db,
            identity=identity,
            storage_path=Path(reusable_asset.storage_path),
            mime_type=reusable_asset.mime_type,
        )
        asset.byte_size = reusable_asset.byte_size
        asset.status = AUDIO_STATUS_READY
        asset.generation_error = None
        db.flush()
        return asset, True

    storage_path = _word_audio_path(identity=identity)
    asset = create_or_update_word_audio_asset(
        db,
        identity=identity,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    audio_bytes = client.synthesize(text=identity.source_text)
    _write_audio_bytes(storage_path=storage_path, payload=audio_bytes)
    asset.byte_size = len(audio_bytes)
    asset.status = AUDIO_STATUS_READY
    asset.generation_error = None
    db.flush()
    return asset, False


def mark_sentence_audio_asset_failed(
    db: Session,
    *,
    sentence_id: str,
    error_message: str,
) -> None:
    sentence = db.get(Sentence, sentence_id)
    if sentence is None:
        return
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        return
    identity = sentence_audio_identity(
        sentence=sentence,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    storage_path = _sentence_audio_path(identity=identity)
    asset = create_or_update_sentence_audio_asset(
        db,
        identity=identity,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset.status = AUDIO_STATUS_FAILED
    asset.generation_error = error_message
    db.flush()


def mark_word_audio_asset_failed(
    db: Session,
    *,
    word_id: str,
    error_message: str,
) -> None:
    word = db.get(Word, word_id)
    if word is None:
        return
    settings = get_settings()
    voice_id = settings.elevenlabs_voice_id
    if voice_id is None:
        return
    identity = word_audio_identity(
        word=word,
        provider=AUDIO_PROVIDER_ELEVENLABS,
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
    )
    storage_path = _word_audio_path(identity=identity)
    asset = create_or_update_word_audio_asset(
        db,
        identity=identity,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset.status = AUDIO_STATUS_FAILED
    asset.generation_error = error_message
    db.flush()


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
    if asset.status != AUDIO_STATUS_READY or not Path(asset.storage_path).exists():
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
    if asset.status != AUDIO_STATUS_READY or not Path(asset.storage_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word audio not available")
    return asset


def _sentence_audio_path(*, identity: SentenceAudioIdentity) -> Path:
    root = get_settings().sentence_audio_storage_root
    return root / identity.provider / identity.voice_id / f"{identity.text_hash}.mp3"


def _word_audio_path(*, identity: WordAudioIdentity) -> Path:
    root = get_settings().word_audio_storage_root
    return root / identity.provider / identity.voice_id / f"{identity.text_hash}.mp3"


def _write_audio_bytes(*, storage_path: Path, payload: bytes) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = storage_path.with_suffix(f"{storage_path.suffix}.tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(storage_path)


def _normalize_audio_text(text: str) -> str:
    return " ".join(text.split())


def _audio_text_digest(*, provider: str, voice_id: str, model_id: str, normalized_text: str) -> str:
    return sha256(f"{provider}:{voice_id}:{model_id}:{normalized_text}".encode()).hexdigest()


def _asset_file_exists(asset: SentenceAudioAsset | WordAudioAsset) -> bool:
    return asset.status == AUDIO_STATUS_READY and Path(asset.storage_path).exists()
