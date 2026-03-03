from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from typing import Literal, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.learning.schemas import (
    HintSpan,
    ItemResult,
    LessonItemResponse,
    SentenceTokenPreview,
    SubmitRequest,
    SubmitResponse,
)
from domain.auth.models import UserCourseEnrollment
from domain.content.display import (
    append_alternate_script_hint,
    display_sentence_text_ja,
    display_sentence_unit_surface,
    display_word_ja,
    lesson_uses_kana_display,
)
from domain.content.models import (
    Item,
    ItemKanjiKanaMatch,
    ItemSentenceTiles,
    ItemWordChoice,
    Lesson,
    LessonWord,
    Section,
    Sentence,
    SentenceTile,
    SentenceTileSet,
    SentenceUnit,
    SentenceWordLink,
    Unit,
    Word,
)
from domain.explain.models import SentenceUnitHint
from domain.learning.models import ExamAttempt, UserLessonProgress

EXAM_PASS_THRESHOLD = 0.8
WORD_CHOICE_OPTION_COUNT = 4


def _stable_shuffle_options(*, seed: str, options: list[str]) -> list[str]:
    decorated = [
        (
            hashlib.sha256(f"{seed}:{index}:{option}".encode()).hexdigest(),
            option,
        )
        for index, option in enumerate(options)
    ]
    decorated.sort(key=lambda item: item[0])
    return [option for _digest, option in decorated]


def _get_lesson_in_course(db: Session, course_version_id: str, lesson_id: str) -> Lesson:
    lesson = db.scalar(
        select(Lesson)
        .join(Unit, Unit.id == Lesson.unit_id)
        .join(Section, Section.id == Unit.section_id)
        .where(Section.course_version_id == course_version_id, Lesson.id == lesson_id)
    )
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


def _get_items_for_lesson(db: Session, lesson_id: str) -> list[Item]:
    return list(db.scalars(select(Item).where(Item.lesson_id == lesson_id).order_by(Item.order_index.asc())))


@dataclass(frozen=True, slots=True)
class _LessonItemOrderMeta:
    item: Item
    word_id: str | None
    sentence_id: str | None
    is_ja_en_sentence: bool
    is_en_ja_sentence: bool
    is_kana_kanji_match: bool
    is_word_choice: bool


def _shuffle_digest(*, lesson_id: str, item_id: str) -> str:
    return hashlib.sha256(f"{lesson_id}:{item_id}:lesson-order".encode()).hexdigest()


def _build_order_meta_by_item_id(db: Session, *, items: list[Item]) -> dict[str, _LessonItemOrderMeta]:
    item_ids = [item.id for item in items]
    word_choice_payloads = {
        payload.item_id: payload
        for payload in db.scalars(select(ItemWordChoice).where(ItemWordChoice.item_id.in_(item_ids)))
    }
    sentence_payloads = {
        payload.item_id: payload
        for payload in db.scalars(select(ItemSentenceTiles).where(ItemSentenceTiles.item_id.in_(item_ids)))
    }
    kanji_payloads = {
        payload.item_id: payload
        for payload in db.scalars(select(ItemKanjiKanaMatch).where(ItemKanjiKanaMatch.item_id.in_(item_ids)))
    }
    return {
        item.id: _LessonItemOrderMeta(
            item=item,
            word_id=word_choice_payloads[item.id].word_id
            if item.id in word_choice_payloads
            else kanji_payloads[item.id].word_id
            if item.id in kanji_payloads
            else None,
            sentence_id=sentence_payloads[item.id].sentence_id if item.id in sentence_payloads else None,
            is_ja_en_sentence=item.type == "sentence_tiles" and item.prompt_lang == "ja" and item.answer_lang == "en",
            is_en_ja_sentence=item.type == "sentence_tiles" and item.prompt_lang == "en" and item.answer_lang == "ja",
            is_kana_kanji_match=(
                item.type == "kanji_kana_match"
                and item.id in kanji_payloads
                and kanji_payloads[item.id].prompt_script == "kana"
                and kanji_payloads[item.id].answer_script == "kanji"
            ),
            is_word_choice=item.type == "word_choice",
        )
        for item in items
    }


def _sentence_word_ids_by_sentence_id(db: Session, *, sentence_ids: list[str]) -> dict[str, set[str]]:
    if not sentence_ids:
        return {}
    rows = db.execute(
        select(SentenceWordLink.sentence_id, SentenceWordLink.word_id).where(SentenceWordLink.sentence_id.in_(sentence_ids))
    ).all()
    word_ids_by_sentence_id: dict[str, set[str]] = defaultdict(set)
    for sentence_id, word_id in rows:
        word_ids_by_sentence_id[sentence_id].add(word_id)
    return dict(word_ids_by_sentence_id)


def _topologically_shuffled_items(
    *,
    lesson_id: str,
    items: list[Item],
    meta_by_item_id: dict[str, _LessonItemOrderMeta],
    sentence_word_ids_by_sentence_id: dict[str, set[str]],
) -> list[Item]:
    predecessors_by_item_id: dict[str, set[str]] = {item.id: set() for item in items}
    word_choice_ids_by_word_id: dict[str, list[str]] = defaultdict(list)
    kana_match_ids_by_word_id: dict[str, list[str]] = defaultdict(list)
    ja_en_sentence_ids_by_sentence_id: dict[str, list[str]] = defaultdict(list)
    en_ja_sentence_ids_by_sentence_id: dict[str, list[str]] = defaultdict(list)
    sentence_item_ids_by_sentence_id: dict[str, list[str]] = defaultdict(list)

    for item in items:
        meta = meta_by_item_id[item.id]
        if meta.word_id is not None and meta.is_word_choice:
            word_choice_ids_by_word_id[meta.word_id].append(item.id)
        if meta.word_id is not None and meta.is_kana_kanji_match:
            kana_match_ids_by_word_id[meta.word_id].append(item.id)
        if meta.sentence_id is not None:
            sentence_item_ids_by_sentence_id[meta.sentence_id].append(item.id)
            if meta.is_ja_en_sentence:
                ja_en_sentence_ids_by_sentence_id[meta.sentence_id].append(item.id)
            if meta.is_en_ja_sentence:
                en_ja_sentence_ids_by_sentence_id[meta.sentence_id].append(item.id)

    for sentence_id, en_ja_ids in en_ja_sentence_ids_by_sentence_id.items():
        for en_ja_item_id in en_ja_ids:
            predecessors_by_item_id[en_ja_item_id].update(ja_en_sentence_ids_by_sentence_id.get(sentence_id, []))

    for word_id, kana_match_ids in kana_match_ids_by_word_id.items():
        sentence_ids = [
            sentence_id
            for sentence_id, sentence_word_ids in sentence_word_ids_by_sentence_id.items()
            if word_id in sentence_word_ids
        ]
        for kana_match_item_id in kana_match_ids:
            for word_choice_item_id in word_choice_ids_by_word_id.get(word_id, []):
                predecessors_by_item_id[word_choice_item_id].add(kana_match_item_id)
            for sentence_id in sentence_ids:
                for sentence_item_id in sentence_item_ids_by_sentence_id.get(sentence_id, []):
                    predecessors_by_item_id[sentence_item_id].add(kana_match_item_id)

    for word_id, word_choice_ids in word_choice_ids_by_word_id.items():
        sentence_ids = [
            sentence_id
            for sentence_id, sentence_word_ids in sentence_word_ids_by_sentence_id.items()
            if word_id in sentence_word_ids
        ]
        for word_choice_item_id in word_choice_ids:
            for sentence_id in sentence_ids:
                for sentence_item_id in sentence_item_ids_by_sentence_id.get(sentence_id, []):
                    predecessors_by_item_id[sentence_item_id].add(word_choice_item_id)

    remaining_item_ids = {item.id for item in items}
    ordered_items: list[Item] = []
    while remaining_item_ids:
        available_item_ids = sorted(
            [item_id for item_id in remaining_item_ids if predecessors_by_item_id[item_id].isdisjoint(remaining_item_ids)],
            key=lambda item_id: _shuffle_digest(lesson_id=lesson_id, item_id=item_id),
        )
        if not available_item_ids:
            return items
        next_item_id = available_item_ids[0]
        ordered_items.append(meta_by_item_id[next_item_id].item)
        remaining_item_ids.remove(next_item_id)
    return ordered_items


def _ordered_items_for_lesson(db: Session, *, lesson: Lesson) -> list[Item]:
    items = _get_items_for_lesson(db, lesson.id)
    if lesson.kind != "normal" or len(items) <= 1:
        return items
    meta_by_item_id = _build_order_meta_by_item_id(db, items=items)
    sentence_ids = [meta.sentence_id for meta in meta_by_item_id.values() if meta.sentence_id is not None]
    return _topologically_shuffled_items(
        lesson_id=lesson.id,
        items=items,
        meta_by_item_id=meta_by_item_id,
        sentence_word_ids_by_sentence_id=_sentence_word_ids_by_sentence_id(
            db, sentence_ids=list(dict.fromkeys(sentence_ids))
        ),
    )


def _normalize_answer(answer: str) -> str:
    return " ".join(answer.split()).strip()


def _upsert_progress(db: Session, enrollment_id: str, lesson_id: str, state: str) -> None:
    progress = db.get(UserLessonProgress, {"enrollment_id": enrollment_id, "lesson_id": lesson_id})
    if progress is None:
        db.add(UserLessonProgress(enrollment_id=enrollment_id, lesson_id=lesson_id, state=state))
        return
    progress.state = state
    progress.updated_at = datetime.now(UTC)


def _load_sentence_tokens(db: Session, sentence_id: str, lang: str = "ja") -> list[SentenceUnit]:
    return list(
        db.scalars(
            select(SentenceUnit)
            .where(SentenceUnit.sentence_id == sentence_id, SentenceUnit.lang == lang)
            .order_by(SentenceUnit.unit_index.asc())
        )
    )


def _load_sentence_hints(db: Session, sentence_id: str) -> tuple[dict[int, list[str]], list[HintSpan]]:
    hint_rows = list(
        db.scalars(
            select(SentenceUnitHint)
            .where(SentenceUnitHint.sentence_id == sentence_id, SentenceUnitHint.lang == "ja")
            .order_by(SentenceUnitHint.unit_index.asc())
        )
    )
    hints_by_token: dict[int, list[str]] = {}
    spans: list[HintSpan] = []
    for hint in hint_rows:
        hints_by_token.setdefault(hint.unit_index, []).append(hint.hint_text)
        spans.append(
            HintSpan(
                token_start=hint.unit_index,
                token_end=hint.unit_index,
                hint_text=hint.hint_text,
                hint_kind=hint.hint_kind,
            )
        )
    return hints_by_token, spans


def _build_reverse_hints_for_en(
    ja_tokens: list[SentenceUnit],
    ja_hints_by_token: dict[int, list[str]],
    en_tokens: list[SentenceUnit],
) -> dict[int, list[str]]:
    """Map English tokens to Japanese glosses by matching English surfaces to Japanese hint texts."""
    gloss_to_ja: dict[str, list[str]] = {}
    for ja_token in ja_tokens:
        ja_label = ja_token.surface
        if ja_token.reading and ja_token.reading != ja_token.surface:
            ja_label = f"{ja_token.surface} ({ja_token.reading})"
        for hint_text in ja_hints_by_token.get(ja_token.unit_index, []):
            for fragment in hint_text.split(","):
                gloss_to_ja.setdefault(fragment.strip().lower(), []).append(ja_label)

    en_hints: dict[int, list[str]] = {}
    for en_token in en_tokens:
        key = en_token.surface.lower()
        if key in gloss_to_ja:
            en_hints[en_token.unit_index] = gloss_to_ja[key]
    return en_hints


def _serialize_tokens(
    tokens: list[SentenceUnit],
    hints_by_token: dict[int, list[str]] | None = None,
    *,
    use_kana: bool = False,
) -> list[SentenceTokenPreview]:
    return [
        SentenceTokenPreview(
            token_index=token.unit_index,
            surface=display_sentence_unit_surface(token, use_kana=use_kana),
            lemma=token.lemma,
            reading=token.reading,
            pos=token.pos,
            hints=append_alternate_script_hint(
                list((hints_by_token or {}).get(token.unit_index, [])),
                displayed_surface=display_sentence_unit_surface(token, use_kana=use_kana),
                lemma=token.lemma,
                reading=token.reading,
                use_kana=use_kana,
            ),
        )
        for token in tokens
    ]


def _get_word_answer_display(word: Word, *, answer_lang: str) -> str:
    if answer_lang == "en":
        return word.gloss_primary_en
    return display_word_ja(word, use_kana=False)


def _word_candidate_rank(*, target: Word, candidate: Word) -> tuple[int, int, int, str]:
    same_pos_rank = 0 if candidate.pos == target.pos else 1
    difficulty_rank = abs(candidate.intro_order - target.intro_order)
    script_rank = len(candidate.canonical_writing_ja)
    return (same_pos_rank, difficulty_rank, script_rank, candidate.canonical_writing_ja)


def _lesson_word_candidates(db: Session, *, lesson_id: str) -> list[Word]:
    return list(
        db.scalars(
            select(Word)
            .join(LessonWord, LessonWord.word_id == Word.id)
            .where(LessonWord.lesson_id == lesson_id)
            .order_by(Word.intro_order.asc(), Word.canonical_writing_ja.asc())
        )
    )


def _build_sentence_tile_options(
    db: Session,
    *,
    answer_lang: str,
    correct_tiles: list[str],
    distractor_count: int,
    lesson_id: str,
    course_version_id: str,
    use_kana: bool,
) -> list[str]:
    existing_tiles = set(correct_tiles)

    def distractor_display(word: Word) -> str:
        if answer_lang == "en":
            return _get_word_answer_display(word, answer_lang=answer_lang).strip()
        return display_word_ja(word, use_kana=use_kana).strip()

    lesson_candidates = _lesson_word_candidates(db, lesson_id=lesson_id)
    course_candidates = _course_word_candidates(db, course_version_id=course_version_id)
    distractor_candidates: list[str] = []

    for candidate_word in [*lesson_candidates, *course_candidates]:
        candidate_display = distractor_display(candidate_word)
        if not candidate_display:
            continue
        if any(character.isspace() for character in candidate_display):
            continue
        if candidate_display in existing_tiles or candidate_display in distractor_candidates:
            continue
        distractor_candidates.append(candidate_display)
        if len(distractor_candidates) == distractor_count:
            break

    return _stable_shuffle_options(
        seed=f"{lesson_id}:{course_version_id}:{answer_lang}:sentence_tiles",
        options=[*correct_tiles, *distractor_candidates],
    )


def _course_word_candidates(db: Session, *, course_version_id: str) -> list[Word]:
    return list(
        db.scalars(
            select(Word)
            .where(Word.course_version_id == course_version_id)
            .order_by(Word.intro_order.asc(), Word.canonical_writing_ja.asc())
        )
    )


def _build_word_choice_options(
    db: Session, *, lesson_id: str, target_word: Word, answer_lang: str, use_kana: bool
) -> list[str]:
    correct_answer = (
        _get_word_answer_display(target_word, answer_lang=answer_lang)
        if answer_lang == "en"
        else display_word_ja(target_word, use_kana=use_kana)
    )
    candidate_words = _lesson_word_candidates(db, lesson_id=lesson_id)
    if len(candidate_words) < WORD_CHOICE_OPTION_COUNT:
        candidate_words = _course_word_candidates(db, course_version_id=target_word.course_version_id)

    distractor_candidates = [
        (
            _get_word_answer_display(candidate, answer_lang=answer_lang)
            if answer_lang == "en"
            else display_word_ja(candidate, use_kana=use_kana)
        )
        for candidate in sorted(
            (word for word in candidate_words if word.id != target_word.id),
            key=lambda candidate: _word_candidate_rank(target=target_word, candidate=candidate),
        )
        if (
            _get_word_answer_display(candidate, answer_lang=answer_lang)
            if answer_lang == "en"
            else display_word_ja(candidate, use_kana=use_kana)
        )
        != correct_answer
    ]
    unique_distractors: list[str] = []
    for distractor in distractor_candidates:
        if distractor not in unique_distractors:
            unique_distractors.append(distractor)
        if len(unique_distractors) == WORD_CHOICE_OPTION_COUNT - 1:
            break

    options = [correct_answer, *unique_distractors]
    if len(options) == 1:
        return options
    return options[:WORD_CHOICE_OPTION_COUNT]


def _build_kanji_kana_options(
    db: Session,
    *,
    lesson_id: str,
    target_word: Word,
    prompt_script: str,
    answer_script: str,
) -> list[str]:
    if prompt_script == "kanji" and answer_script == "kana":
        correct_answer = target_word.reading_kana
    elif prompt_script == "kana" and answer_script == "kanji":
        correct_answer = target_word.canonical_writing_ja
    else:
        msg = f"Unsupported kanji-kana direction: {prompt_script}->{answer_script}"
        raise ValueError(msg)
    candidate_words = _lesson_word_candidates(db, lesson_id=lesson_id)
    if len(candidate_words) < WORD_CHOICE_OPTION_COUNT:
        candidate_words = _course_word_candidates(db, course_version_id=target_word.course_version_id)
    distractors: list[str] = []
    for candidate in candidate_words:
        if candidate.id == target_word.id:
            continue
        candidate_answer = (
            candidate.reading_kana if answer_script == "kana" else candidate.canonical_writing_ja
        )
        if candidate_answer == correct_answer or candidate_answer in distractors:
            continue
        if candidate.reading_kana == candidate.canonical_writing_ja:
            continue
        distractors.append(candidate_answer)
        if len(distractors) == WORD_CHOICE_OPTION_COUNT - 1:
            break
    return _stable_shuffle_options(
        seed=f"{lesson_id}:{target_word.id}:kanji-kana:{prompt_script}:{answer_script}",
        options=[correct_answer, *distractors],
    )


@dataclass(slots=True)
class _ItemPayload:
    prompt_text: str
    expected_answer: str
    answer_tiles: list[str]
    sentence_id: str | None
    sentence_ja_tokens: list[SentenceTokenPreview]
    sentence_ja_hints: list[HintSpan]
    sentence_en_tokens: list[SentenceTokenPreview]


def _item_payload(db: Session, item: Item) -> _ItemPayload:
    use_kana = lesson_uses_kana_display(db, lesson_id=item.lesson_id)
    if item.type == "sentence_tiles":
        tile_payload = db.get(ItemSentenceTiles, item.id)
        if tile_payload is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing sentence tile payload"
            )
        sentence = db.get(Sentence, tile_payload.sentence_id)
        tile_set = db.get(SentenceTileSet, tile_payload.tile_set_id)
        if sentence is None or tile_set is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Broken sentence tile item references"
            )
        tiles = list(
            db.scalars(
                select(SentenceTile)
                .where(SentenceTile.tile_set_id == tile_set.id)
                .order_by(SentenceTile.tile_index.asc())
            )
        )
        if not tiles:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing sentence tiles")
        ja_tokens = _load_sentence_tokens(db, sentence.id, lang="ja")
        prompt_text = (
            sentence.en_text
            if item.prompt_lang == "en"
            else display_sentence_text_ja(sentence=sentence, units=ja_tokens, use_kana=use_kana)
        )
        displayed_correct_tiles = [
            tile.text
            if item.answer_lang == "en"
            else "".join(
                display_sentence_unit_surface(unit, use_kana=use_kana)
                for unit in ja_tokens
                if tile.unit_start is not None
                and tile.unit_end is not None
                and tile.unit_start <= unit.unit_index <= tile.unit_end
            )
            for tile in tiles
        ]
        expected_answer = " ".join(displayed_correct_tiles).strip()
        answer_tiles = _build_sentence_tile_options(
            db,
            answer_lang=item.answer_lang,
            correct_tiles=displayed_correct_tiles,
            distractor_count=2,
            lesson_id=item.lesson_id,
            course_version_id=sentence.course_version_id,
            use_kana=use_kana,
        )
        ja_hints_by_token, ja_hint_spans = _load_sentence_hints(db, sentence.id)

        en_tokens = _load_sentence_tokens(db, sentence.id, lang="en")
        en_hints = _build_reverse_hints_for_en(ja_tokens, ja_hints_by_token, en_tokens)

        return _ItemPayload(
            prompt_text=prompt_text,
            expected_answer=expected_answer,
            answer_tiles=answer_tiles,
            sentence_id=sentence.id,
            sentence_ja_tokens=_serialize_tokens(ja_tokens, ja_hints_by_token, use_kana=use_kana),
            sentence_ja_hints=ja_hint_spans,
            sentence_en_tokens=_serialize_tokens(en_tokens, en_hints),
        )

    if item.type == "kanji_kana_match":
        kanji_kana_payload = db.get(ItemKanjiKanaMatch, item.id)
        if kanji_kana_payload is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Missing kanji-kana payload",
            )
        word = db.get(Word, kanji_kana_payload.word_id)
        if word is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing target word")
        prompt_text = (
            word.canonical_writing_ja
            if kanji_kana_payload.prompt_script == "kanji"
            else word.reading_kana
        )
        expected_answer = (
            word.reading_kana
            if kanji_kana_payload.answer_script == "kana"
            else word.canonical_writing_ja
        )
        ja_token = SentenceTokenPreview(
            token_index=0,
            surface=prompt_text,
            lemma=word.canonical_writing_ja,
            reading=word.reading_kana,
            pos=word.pos,
            hints=[word.gloss_primary_en],
        )
        return _ItemPayload(
            prompt_text=prompt_text,
            expected_answer=expected_answer,
            answer_tiles=_build_kanji_kana_options(
                db,
                lesson_id=item.lesson_id,
                target_word=word,
                prompt_script=kanji_kana_payload.prompt_script,
                answer_script=kanji_kana_payload.answer_script,
            ),
            sentence_id=None,
            sentence_ja_tokens=[ja_token],
            sentence_ja_hints=[],
            sentence_en_tokens=[],
        )

    if item.type == "word_choice":
        word_choice_payload = db.get(ItemWordChoice, item.id)
        if word_choice_payload is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing word-choice payload")
        word = db.get(Word, word_choice_payload.word_id)
        if word is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing target word")
        prompt_text = display_word_ja(word, use_kana=use_kana) if item.prompt_lang == "ja" else word.gloss_primary_en
        expected_answer = (
            _get_word_answer_display(word, answer_lang=item.answer_lang)
            if item.answer_lang == "en"
            else display_word_ja(word, use_kana=use_kana)
        )

        displayed_ja = display_word_ja(word, use_kana=use_kana)
        has_kanji = any(
            "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" or "\uf900" <= ch <= "\ufaff"
            for ch in word.canonical_writing_ja
        )

        # Hints for the Japanese prompt: primary gloss, alternatives, then kanji/kana alternate form
        ja_hints: list[str] = [word.gloss_primary_en, *word.gloss_alternatives_en]
        if has_kanji:
            if use_kana:
                ja_hints.append(word.canonical_writing_ja)
            else:
                ja_hints.append(word.reading_kana)

        ja_token = SentenceTokenPreview(
            token_index=0,
            surface=displayed_ja,
            lemma=word.canonical_writing_ja,
            reading=word.reading_kana,
            pos=word.pos,
            hints=ja_hints,
        )

        # Hints for the English prompt: kanji+reading, alternatives
        ja_label = f"{word.canonical_writing_ja} ({word.reading_kana})" if has_kanji else word.canonical_writing_ja
        word_en_hints: list[str] = [ja_label, *word.gloss_alternatives_en]

        en_token = SentenceTokenPreview(
            token_index=0,
            surface=word.gloss_primary_en,
            lemma=word.gloss_primary_en,
            reading=None,
            pos=word.pos,
            hints=word_en_hints,
        )

        return _ItemPayload(
            prompt_text=prompt_text,
            expected_answer=expected_answer,
            answer_tiles=_build_word_choice_options(
                db, lesson_id=item.lesson_id, target_word=word, answer_lang=item.answer_lang, use_kana=use_kana
            ),
            sentence_id=None,
            sentence_ja_tokens=[ja_token],
            sentence_ja_hints=[],
            sentence_en_tokens=[en_token],
        )

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unsupported item type: {item.type}")


def get_next_item(db: Session, enrollment: UserCourseEnrollment, lesson_id: str, cursor: int) -> LessonItemResponse:
    lesson = _get_lesson_in_course(db, enrollment.course_version_id, lesson_id)
    items = _ordered_items_for_lesson(db, lesson=lesson)
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson has no items")
    if cursor < 0 or cursor >= len(items):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No more items")

    item = items[cursor]
    p = _item_payload(db, item)
    return LessonItemResponse(
        item_id=item.id,
        lesson_id=lesson.id,
        lesson_kind=lesson.kind,
        item_type=cast(Literal["word_choice", "sentence_tiles", "kanji_kana_match"], item.type),
        order_index=item.order_index,
        cursor=cursor,
        total_items=len(items),
        is_last_item=cursor == len(items) - 1,
        prompt_lang=item.prompt_lang,
        answer_lang=item.answer_lang,
        prompt_text=p.prompt_text,
        sentence_id=p.sentence_id,
        sentence_ja_tokens=p.sentence_ja_tokens,
        sentence_ja_hints=p.sentence_ja_hints,
        sentence_en_tokens=p.sentence_en_tokens,
        answer_tiles=p.answer_tiles,
    )


def submit_lesson(
    db: Session,
    *,
    enrollment: UserCourseEnrollment,
    lesson_id: str,
    payload: SubmitRequest,
) -> SubmitResponse:
    lesson = _get_lesson_in_course(db, enrollment.course_version_id, lesson_id)
    items = _ordered_items_for_lesson(db, lesson=lesson)
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson has no items")
    if len(payload.answers) > len(items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submitted more answers than there are items in the lesson",
        )

    items_by_id = {item.id: item for item in items}
    results: list[ItemResult] = []
    correct_items = 0
    for answer in payload.answers:
        item = items_by_id.get(answer.item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Item {answer.item_id} not found in lesson"
            )
        p = _item_payload(db, item)
        normalized_expected = _normalize_answer(p.expected_answer)
        normalized_user = _normalize_answer(answer.user_answer)
        is_correct = normalized_expected == normalized_user
        if is_correct:
            correct_items += 1
        results.append(
            ItemResult(
                item_id=item.id,
                expected_answer=p.expected_answer,
                user_answer=answer.user_answer,
                is_correct=is_correct,
            )
        )

    is_full_submission = len(payload.answers) == len(items)
    score = correct_items / len(items) if is_full_submission else correct_items / max(len(payload.answers), 1)
    if is_full_submission:
        passed = score >= EXAM_PASS_THRESHOLD if lesson.kind == "exam" else correct_items == len(items)
        progress_state = "completed" if passed else "in_progress"
        _upsert_progress(db, enrollment.id, lesson.id, progress_state)
    else:
        passed = correct_items == len(payload.answers)
        progress_state = "in_progress"
        _upsert_progress(db, enrollment.id, lesson.id, progress_state)

    if lesson.kind == "exam" and is_full_submission:
        attempt_no = (
            db.scalar(
                select(ExamAttempt.attempt_no)
                .where(ExamAttempt.enrollment_id == enrollment.id, ExamAttempt.lesson_id == lesson.id)
                .order_by(ExamAttempt.attempt_no.desc())
                .limit(1)
            )
            or 0
        )
        db.add(
            ExamAttempt(
                enrollment_id=enrollment.id,
                lesson_id=lesson.id,
                attempt_no=attempt_no + 1,
                submitted_at=datetime.now(UTC),
                score=score,
                passed=passed,
            )
        )

    db.commit()
    return SubmitResponse(
        lesson_id=lesson.id,
        lesson_kind=lesson.kind,
        score=score,
        correct_items=correct_items,
        total_items=len(items),
        passed=passed,
        progress_state=progress_state,
        item_results=results,
    )
