from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import hashlib

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.kana.schemas import (
    KanaAnswerOption,
    KanaCharacterProgress,
    KanaContinueResponse,
    KanaItemResult,
    KanaLessonItemResponse,
    KanaOverviewResponse,
    KanaScriptGroup,
    KanaSubmitRequest,
    KanaSubmitResponse,
)
from domain.auth.models import UserCourseEnrollment
from domain.kana.audio_service import resolve_kana_audio_url
from domain.kana.catalog import TARGET_EXPOSURES, ensure_kana_catalog_seeded
from domain.kana.constants import (
    KANA_NEARBY_RANK_WINDOW,
    LESSON_ITEM_COUNT,
    LESSON_REPEAT_TARGET_COUNT,
    LESSON_TARGET_UNIQUE_COUNT,
)
from domain.kana.models import KanaCharacter, KanaLesson, KanaLessonItem, UserKanaProgress


def _progress_by_character_id(db: Session, *, enrollment_id: str) -> dict[str, UserKanaProgress]:
    return {
        row.character_id: row
        for row in db.scalars(select(UserKanaProgress).where(UserKanaProgress.enrollment_id == enrollment_id))
    }


def _progress_state(*, character: KanaCharacter, progress: UserKanaProgress | None, unlocked_group_order: int) -> str:
    """Derive UI state. Partial progress is always *learning*, even if the row is locked for new starts."""
    times = 0 if progress is None else progress.times_seen
    if times >= character.target_exposures:
        return "mastered"
    if times > 0:
        return "learning"
    if character.group_order > unlocked_group_order:
        return "locked"
    return "new"


def _times_seen(progress_by_character_id: dict[str, UserKanaProgress], *, character_id: str) -> int:
    progress = progress_by_character_id.get(character_id)
    return progress.times_seen if progress is not None else 0


def _eligible_characters(
    *,
    characters: list[KanaCharacter],
    progress_by_character_id: dict[str, UserKanaProgress],
) -> list[KanaCharacter]:
    eligible: list[KanaCharacter] = []
    seen_by_char = {
        char.char: progress_by_character_id[char.id].times_seen for char in characters if char.id in progress_by_character_id
    }
    for character in characters:
        if progress_by_character_id.get(character.id) is not None and progress_by_character_id[character.id].times_seen >= character.target_exposures:
            continue
        if character.base_char is not None and seen_by_char.get(character.base_char, 0) <= 0:
            continue
        eligible.append(character)
    return eligible


def _choice_pool(
    *,
    target: KanaCharacter,
    characters: list[KanaCharacter],
) -> list[KanaCharacter]:
    same_script = [candidate for candidate in characters if candidate.script == target.script and candidate.id != target.id]
    same_group = [candidate for candidate in same_script if candidate.group_key == target.group_key]
    nearby = [
        candidate
        for candidate in same_script
        if abs(candidate.difficulty_rank - target.difficulty_rank) <= KANA_NEARBY_RANK_WINDOW and candidate.id != target.id
    ]
    ordered: list[KanaCharacter] = []
    seen_ids: set[str] = set()
    for candidate in same_group + nearby + same_script + [candidate for candidate in characters if candidate.id != target.id]:
        if candidate.id in seen_ids:
            continue
        ordered.append(candidate)
        seen_ids.add(candidate.id)
    return ordered


def _locked_state_for_group(*, group_order: int, script: str, unlocked_hiragana_group_order: int) -> str:
    if script == "hiragana":
        return "locked" if group_order > unlocked_hiragana_group_order else "available"
    katakana_group_threshold = unlocked_hiragana_group_order + 20
    return "locked" if group_order > katakana_group_threshold else "available"


def _stable_shuffle[T](items: list[T], *, seed: str) -> list[T]:
    decorated = [
        (
            hashlib.sha256(f"{seed}:{index}".encode()).hexdigest(),
            item,
        )
        for index, item in enumerate(items)
    ]
    decorated.sort(key=lambda entry: entry[0])
    return [item for _digest, item in decorated]


def _upsert_character_progress(
    db: Session,
    *,
    enrollment_id: str,
    character_id: str,
    prompted_as_audio_count: int,
    prompted_as_character_count: int,
    seen_increment: int,
) -> None:
    progress = db.get(UserKanaProgress, {"enrollment_id": enrollment_id, "character_id": character_id})
    if progress is None:
        progress = UserKanaProgress(
            enrollment_id=enrollment_id,
            character_id=character_id,
            times_seen=0,
            times_prompted_as_character=0,
            times_prompted_as_audio=0,
            state="new",
        )
        db.add(progress)
    progress.times_seen += seen_increment
    progress.times_prompted_as_audio += prompted_as_audio_count
    progress.times_prompted_as_character += prompted_as_character_count
    progress.state = "mastered" if progress.times_seen >= TARGET_EXPOSURES else "learning"
    progress.updated_at = datetime.now(UTC)


def _get_kana_lesson_or_404(db: Session, *, enrollment_id: str, lesson_id: str) -> KanaLesson:
    lesson = db.get(KanaLesson, lesson_id)
    if lesson is None or lesson.enrollment_id != enrollment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kana lesson not found")
    return lesson


def _planned_lesson_prompt_character_ids(db: Session, *, lesson_id: str) -> set[str]:
    rows = db.scalars(select(KanaLessonItem.prompt_character_id).where(KanaLessonItem.lesson_id == lesson_id))
    return set(rows)


def _load_ordered_kana_characters(db: Session) -> list[KanaCharacter]:
    return list(db.scalars(select(KanaCharacter).order_by(KanaCharacter.difficulty_rank.asc())))


def _scalar_planned_lesson_id(db: Session, *, enrollment_id: str) -> str | None:
    return db.scalar(
        select(KanaLesson.id)
        .where(KanaLesson.enrollment_id == enrollment_id, KanaLesson.status == "planned")
        .order_by(KanaLesson.created_at.desc(), KanaLesson.id.desc())
        .limit(1)
    )


def _unlocked_hiragana_group_order(
    *,
    characters: list[KanaCharacter],
    eligible: list[KanaCharacter],
) -> int:
    first_hiragana_eligible = next((character for character in eligible if character.script == "hiragana"), None)
    if first_hiragana_eligible is not None:
        return first_hiragana_eligible.group_order + 1
    return max((character.group_order for character in characters if character.script == "hiragana"), default=0)


def _kana_character_progress_row(
    db: Session,
    *,
    character: KanaCharacter,
    progress: UserKanaProgress | None,
    unlocked_hiragana_group_order: int,
    current_lesson_id: str | None,
    planned_prompt_ids: set[str],
) -> tuple[KanaCharacterProgress, int]:
    locked_state = _locked_state_for_group(
        group_order=character.group_order,
        script=character.script,
        unlocked_hiragana_group_order=unlocked_hiragana_group_order,
    )
    state = _progress_state(
        character=character,
        progress=progress,
        unlocked_group_order=character.group_order if locked_state == "available" else -1,
    )
    times_seen_val = progress.times_seen if progress is not None else 0
    in_planned_lesson = current_lesson_id is not None and character.id in planned_prompt_ids
    # Planned lesson may still drill characters in rows that are "locked" for brand-new starts;
    # surface them as *new* so the client can highlight upcoming targets (not *locked* grey).
    if in_planned_lesson and times_seen_val == 0 and state == "locked":
        state = "new"
    mastered_increment = 1 if state == "mastered" else 0
    is_next_lesson_new = (
        current_lesson_id is not None and character.id in planned_prompt_ids and times_seen_val == 0
    )
    # Overview lists every character: expose pronunciation whenever an asset exists (discovery UX).
    row = KanaCharacterProgress(
        character_id=character.id,
        char=character.char,
        script=character.script,
        group_key=character.group_key,
        audio_url=resolve_kana_audio_url(db, character_id=character.id),
        times_seen=times_seen_val,
        target_exposures=character.target_exposures,
        state=state,
        is_next_lesson_new=is_next_lesson_new,
    )
    return row, mastered_increment


def get_kana_overview(db: Session, enrollment: UserCourseEnrollment) -> KanaOverviewResponse:
    ensure_kana_catalog_seeded(db)
    characters = _load_ordered_kana_characters(db)
    progress_by_character_id = _progress_by_character_id(db, enrollment_id=enrollment.id)
    eligible = _eligible_characters(characters=characters, progress_by_character_id=progress_by_character_id)
    unlocked_hiragana_group_order = _unlocked_hiragana_group_order(characters=characters, eligible=eligible)
    current_lesson_id = _scalar_planned_lesson_id(db, enrollment_id=enrollment.id)
    planned_prompt_ids = (
        _planned_lesson_prompt_character_ids(db, lesson_id=current_lesson_id)
        if current_lesson_id is not None
        else set()
    )
    grouped: dict[str, list[KanaCharacterProgress]] = defaultdict(list)
    mastered = 0
    for character in characters:
        progress = progress_by_character_id.get(character.id)
        row, inc = _kana_character_progress_row(
            db,
            character=character,
            progress=progress,
            unlocked_hiragana_group_order=unlocked_hiragana_group_order,
            current_lesson_id=current_lesson_id,
            planned_prompt_ids=planned_prompt_ids,
        )
        mastered += inc
        grouped[character.script].append(row)

    return KanaOverviewResponse(
        scripts=[
            KanaScriptGroup(script="hiragana", characters=grouped["hiragana"]),
            KanaScriptGroup(script="katakana", characters=grouped["katakana"]),
        ],
        current_lesson_id=current_lesson_id,
        total_characters=len(characters),
        mastered_characters=mastered,
    )


def _selection_score(
    *,
    character: KanaCharacter,
    progress_by_character_id: dict[str, UserKanaProgress],
    lesson_seed: str,
) -> tuple[int, int, str]:
    seen = _times_seen(progress_by_character_id, character_id=character.id)
    jitter = hashlib.sha256(f"{lesson_seed}:{character.id}".encode()).hexdigest()
    return (seen, character.difficulty_rank, jitter)


def _pick_lesson_targets(
    *,
    characters: list[KanaCharacter],
    eligible: list[KanaCharacter],
    progress_by_character_id: dict[str, UserKanaProgress],
    lesson_seed: str,
) -> list[KanaCharacter]:
    active_review = [
        character
        for character in characters
        if 0 < _times_seen(progress_by_character_id, character_id=character.id) < character.target_exposures
    ]
    frontier = eligible[: max(LESSON_TARGET_UNIQUE_COUNT + 2, 8)]
    candidate_pool = [
        *sorted(frontier, key=lambda character: _selection_score(character=character, progress_by_character_id=progress_by_character_id, lesson_seed=lesson_seed)),
        *sorted(active_review, key=lambda character: _selection_score(character=character, progress_by_character_id=progress_by_character_id, lesson_seed=f"{lesson_seed}:review")),
    ]
    selected: list[KanaCharacter] = []
    seen_ids: set[str] = set()
    used_groups: set[tuple[str, str]] = set()
    for candidate in candidate_pool:
        if candidate.id in seen_ids:
            continue
        group_token = (candidate.script, candidate.group_key)
        if group_token in used_groups and len(selected) < LESSON_TARGET_UNIQUE_COUNT - 1:
            continue
        selected.append(candidate)
        seen_ids.add(candidate.id)
        used_groups.add(group_token)
        if len(selected) >= LESSON_TARGET_UNIQUE_COUNT:
            break
    if len(selected) < LESSON_TARGET_UNIQUE_COUNT:
        for candidate in candidate_pool:
            if candidate.id in seen_ids:
                continue
            selected.append(candidate)
            seen_ids.add(candidate.id)
            if len(selected) >= LESSON_TARGET_UNIQUE_COUNT:
                break
    return selected


def _build_target_sequence(*, chosen: list[KanaCharacter], lesson_seed: str) -> list[KanaCharacter]:
    ordered = sorted(
        chosen,
        key=lambda character: hashlib.sha256(f"{lesson_seed}:target:{character.id}".encode()).hexdigest(),
    )
    if not ordered:
        return []
    repeated_targets = ordered[: min(LESSON_REPEAT_TARGET_COUNT, len(ordered))]
    sequence = [*ordered, *repeated_targets]
    sequence = _stable_shuffle(sequence, seed=f"{lesson_seed}:sequence")
    while len(sequence) < LESSON_ITEM_COUNT:
        sequence.append(ordered[len(sequence) % len(ordered)])
    return sequence[:LESSON_ITEM_COUNT]


def _create_planned_kana_lesson_for_enrollment(db: Session, enrollment: UserCourseEnrollment) -> KanaLesson | None:
    """Insert a new planned lesson with items, or return None if every kana is already mastered."""
    ensure_kana_catalog_seeded(db)
    characters = _load_ordered_kana_characters(db)
    progress_by_character_id = _progress_by_character_id(db, enrollment_id=enrollment.id)
    eligible = _eligible_characters(characters=characters, progress_by_character_id=progress_by_character_id)
    if not eligible:
        return None

    lesson = KanaLesson(enrollment_id=enrollment.id, status="planned", total_items=LESSON_ITEM_COUNT)
    db.add(lesson)
    db.flush()

    chosen = _pick_lesson_targets(
        characters=characters,
        eligible=eligible,
        progress_by_character_id=progress_by_character_id,
        lesson_seed=lesson.id,
    )
    if not chosen:
        msg = "No kana candidates available for lesson planning"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    target_sequence = _build_target_sequence(chosen=chosen, lesson_seed=lesson.id)
    for order_index, target in enumerate(target_sequence):
        item_type = "audio_to_kana_choice" if order_index % 2 == 0 else "kana_to_audio_choice"
        distractors = _choice_pool(target=target, characters=characters)
        options = [target, *distractors[:3]]
        options = _stable_shuffle(options, seed=f"{lesson.id}:{order_index}:options")
        correct_index = next(index for index, option in enumerate(options) if option.id == target.id)
        db.add(
            KanaLessonItem(
                lesson_id=lesson.id,
                order_index=order_index,
                item_type=item_type,
                prompt_character_id=target.id,
                option_character_ids=[option.id for option in options],
                correct_option_index=correct_index,
            )
        )
    return lesson


def continue_kana_learning(db: Session, enrollment: UserCourseEnrollment) -> KanaContinueResponse:
    """Return the current planned lesson if one exists; otherwise plan the next lesson."""
    existing_id = _scalar_planned_lesson_id(db, enrollment_id=enrollment.id)
    if existing_id is not None:
        lesson = db.get(KanaLesson, existing_id)
        if lesson is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kana lesson not found")
        return KanaContinueResponse(lesson_id=lesson.id, total_items=lesson.total_items)

    lesson = _create_planned_kana_lesson_for_enrollment(db, enrollment)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="All kana are already mastered")
    db.commit()
    return KanaContinueResponse(lesson_id=lesson.id, total_items=lesson.total_items)


def get_next_kana_item(
    db: Session,
    enrollment: UserCourseEnrollment,
    lesson_id: str,
    cursor: int,
) -> KanaLessonItemResponse:
    lesson = _get_kana_lesson_or_404(db, enrollment_id=enrollment.id, lesson_id=lesson_id)
    item = db.scalar(
        select(KanaLessonItem).where(
            KanaLessonItem.lesson_id == lesson.id,
            KanaLessonItem.order_index == cursor,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kana lesson item not found")
    option_characters = {
        character.id: character
        for character in db.scalars(select(KanaCharacter).where(KanaCharacter.id.in_(item.option_character_ids)))
    }
    prompt_character = db.get(KanaCharacter, item.prompt_character_id)
    if prompt_character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kana character not found")
    answer_options = [
        KanaAnswerOption(
            option_id=character_id,
            char=option_characters[character_id].char,
            audio_url=resolve_kana_audio_url(db, character_id=character_id)
            if item.item_type == "kana_to_audio_choice"
            else None,
        )
        for character_id in item.option_character_ids
    ]
    return KanaLessonItemResponse(
        item_id=item.id,
        lesson_id=lesson.id,
        item_type=item.item_type,
        order_index=item.order_index,
        cursor=cursor,
        total_items=lesson.total_items,
        is_last_item=cursor >= lesson.total_items - 1,
        prompt_char=prompt_character.char if item.item_type == "kana_to_audio_choice" else None,
        prompt_audio_url=resolve_kana_audio_url(db, character_id=prompt_character.id)
        if item.item_type == "audio_to_kana_choice"
        else None,
        answer_options=answer_options,
    )


def _progress_deltas_from_lesson_items(items: dict[str, KanaLessonItem]) -> dict[str, dict[str, int]]:
    """Map prompt character id -> {seen, audio, character} increments for a completed lesson."""
    counts_by_character_id: dict[str, dict[str, int]] = defaultdict(
        lambda: {"seen": 0, "audio": 0, "character": 0}
    )
    for item in items.values():
        counts = counts_by_character_id[item.prompt_character_id]
        counts["seen"] += 1
        if item.item_type == "audio_to_kana_choice":
            counts["audio"] += 1
        else:
            counts["character"] += 1
    return counts_by_character_id


def submit_kana_lesson(
    db: Session,
    enrollment: UserCourseEnrollment,
    lesson_id: str,
    payload: KanaSubmitRequest,
) -> KanaSubmitResponse:
    lesson = _get_kana_lesson_or_404(db, enrollment_id=enrollment.id, lesson_id=lesson_id)
    items = {
        item.id: item
        for item in db.scalars(select(KanaLessonItem).where(KanaLessonItem.lesson_id == lesson.id))
    }
    results: list[KanaItemResult] = []
    correct_items = 0
    for answer in payload.answers:
        item = items.get(answer.item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kana lesson item not found")
        expected_option_id = item.option_character_ids[item.correct_option_index]
        is_correct = answer.option_id == expected_option_id
        if is_correct:
            correct_items += 1
        results.append(
            KanaItemResult(
                item_id=item.id,
                expected_option_id=expected_option_id,
                user_option_id=answer.option_id,
                is_correct=is_correct,
            )
        )

    total_items = lesson.total_items
    is_complete_submission = len(results) == total_items
    score = correct_items / total_items if total_items > 0 else 0.0
    passed = is_complete_submission and correct_items == total_items
    if passed:
        lesson.status = "completed"
        lesson.completed_at = datetime.now(UTC)
        for character_id, counts in _progress_deltas_from_lesson_items(items).items():
            _upsert_character_progress(
                db,
                enrollment_id=enrollment.id,
                character_id=character_id,
                prompted_as_audio_count=counts["audio"],
                prompted_as_character_count=counts["character"],
                seen_increment=counts["seen"],
            )
        db.flush()
        # Plan the next lesson immediately so /kana/overview can show upcoming highlights (blue tiles)
        # without requiring a separate POST /kana/continue before the user reopens the grid.
        _create_planned_kana_lesson_for_enrollment(db, enrollment)
    elif is_complete_submission:
        lesson.status = "abandoned"
        lesson.completed_at = datetime.now(UTC)
    db.commit()
    return KanaSubmitResponse(
        lesson_id=lesson.id,
        score=score,
        correct_items=correct_items,
        total_items=total_items,
        passed=passed,
        progress_state="completed" if passed else "abandoned" if is_complete_submission else "planned",
        item_results=results,
    )
