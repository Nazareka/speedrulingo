"""Course-builder workflow audio generation: section ID listing and TTS (ElevenLabs).

Kept out of ``domain.content.audio_service`` so domain stays focused on learner/API audio reads.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from course_builder.integrations.elevenlabs_client import ElevenLabsSpeechClient
from domain.content.audio_service import (
    AUDIO_PROVIDER_ELEVENLABS,
    AUDIO_STATUS_FAILED,
    AUDIO_STATUS_READY,
    MIME_TYPE_MP3,
    SentenceAudioIdentity,
    WordAudioIdentity,
    audio_asset_ready_on_disk,
    create_or_update_audio_asset,
    create_or_update_sentence_audio_asset,
    create_or_update_word_audio_asset,
    get_reusable_audio_asset,
    get_sentence_audio_asset_by_identity,
    get_word_audio_asset_by_identity,
    sentence_audio_identity,
    word_audio_identity,
)
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


def _sentence_audio_path(*, identity: SentenceAudioIdentity) -> Path:
    root = get_settings().audio_storage_root
    return root / identity.audio.provider / identity.audio.voice_id / f"{identity.audio.text_hash}.mp3"


def _word_audio_path(*, identity: WordAudioIdentity) -> Path:
    root = get_settings().audio_storage_root
    return root / identity.audio.provider / identity.audio.voice_id / f"{identity.audio.text_hash}.mp3"


def _write_audio_bytes(*, storage_path: Path, payload: bytes) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = storage_path.with_suffix(f"{storage_path.suffix}.tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(storage_path)


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
    if existing_asset is not None and audio_asset_ready_on_disk(existing_asset):
        return existing_asset, True

    reusable_asset = get_reusable_audio_asset(db, identity=identity.audio)
    if reusable_asset is not None:
        asset = create_or_update_sentence_audio_asset(
            db,
            identity=identity,
            audio_asset=reusable_asset,
            storage_path=Path(reusable_asset.storage_path),
            mime_type=reusable_asset.mime_type,
        )
        asset.byte_size = reusable_asset.byte_size
        asset.status = AUDIO_STATUS_READY
        asset.generation_error = None
        db.flush()
        return asset, True

    storage_path = _sentence_audio_path(identity=identity)
    shared_asset = create_or_update_audio_asset(
        db,
        identity=identity.audio,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset = create_or_update_sentence_audio_asset(
        db,
        identity=identity,
        audio_asset=shared_asset,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    audio_bytes = client.synthesize(text=identity.source_text)
    _write_audio_bytes(storage_path=storage_path, payload=audio_bytes)
    shared_asset.byte_size = len(audio_bytes)
    shared_asset.status = AUDIO_STATUS_READY
    shared_asset.generation_error = None
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
    if existing_asset is not None and audio_asset_ready_on_disk(existing_asset):
        return existing_asset, True

    reusable_asset = get_reusable_audio_asset(db, identity=identity.audio)
    if reusable_asset is not None:
        asset = create_or_update_word_audio_asset(
            db,
            identity=identity,
            audio_asset=reusable_asset,
            storage_path=Path(reusable_asset.storage_path),
            mime_type=reusable_asset.mime_type,
        )
        asset.byte_size = reusable_asset.byte_size
        asset.status = AUDIO_STATUS_READY
        asset.generation_error = None
        db.flush()
        return asset, True

    storage_path = _word_audio_path(identity=identity)
    shared_asset = create_or_update_audio_asset(
        db,
        identity=identity.audio,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset = create_or_update_word_audio_asset(
        db,
        identity=identity,
        audio_asset=shared_asset,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    audio_bytes = client.synthesize(text=identity.source_text)
    _write_audio_bytes(storage_path=storage_path, payload=audio_bytes)
    shared_asset.byte_size = len(audio_bytes)
    shared_asset.status = AUDIO_STATUS_READY
    shared_asset.generation_error = None
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
    shared_asset = create_or_update_audio_asset(
        db,
        identity=identity.audio,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    shared_asset.status = AUDIO_STATUS_FAILED
    shared_asset.generation_error = error_message
    asset = create_or_update_sentence_audio_asset(
        db,
        identity=identity,
        audio_asset=shared_asset,
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
    shared_asset = create_or_update_audio_asset(
        db,
        identity=identity.audio,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    shared_asset.status = AUDIO_STATUS_FAILED
    shared_asset.generation_error = error_message
    asset = create_or_update_word_audio_asset(
        db,
        identity=identity,
        audio_asset=shared_asset,
        storage_path=storage_path,
        mime_type=MIME_TYPE_MP3,
    )
    asset.status = AUDIO_STATUS_FAILED
    asset.generation_error = error_message
    db.flush()
