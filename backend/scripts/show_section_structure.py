from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.engine import SessionLocal
from domain.content.models import (
    Item,
    ItemKanjiKanaMatch,
    ItemSentenceTiles,
    ItemWordChoice,
    Lesson,
    Section,
    Sentence,
    SentenceTile,
    SentenceTileSet,
    Unit,
    Word,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show a simplified unit/lesson/item structure for one course_build section.",
    )
    parser.add_argument("--course-version-id", required=True)
    parser.add_argument("--section-code", required=True)
    parser.add_argument("--unit-index", type=int, required=True)
    parser.add_argument("--lesson-index", type=int, required=True)
    return parser


def _summarize_word_choice(*, db: Session, item: Item) -> dict[str, object]:
    payload = db.get(ItemWordChoice, item.id)
    if payload is None:
        return {"kind": "broken_word_choice", "error": "Missing item_word_choice payload"}
    word = db.get(Word, payload.word_id)
    if word is None:
        return {"kind": "broken_word_choice", "error": "Missing target word"}
    return {
        "kind": "word_choice",
        "prompt": f"{word.canonical_writing_ja} ({word.reading_kana})"
        if item.prompt_lang == "ja"
        else word.gloss_primary_en,
        "correct_answer": word.gloss_primary_en if item.answer_lang == "en" else word.reading_kana,
        "target_word": {
            "canonical_writing_ja": word.canonical_writing_ja,
            "reading_kana": word.reading_kana,
            "gloss_primary_en": word.gloss_primary_en,
            "pos": word.pos,
        },
        "options_shape": f"4 options in {item.answer_lang}",
    }


def _summarize_sentence_tiles(*, db: Session, item: Item) -> dict[str, object]:
    payload = db.get(ItemSentenceTiles, item.id)
    if payload is None:
        return {"kind": "broken_sentence_tiles", "error": "Missing item_sentence_tiles payload"}
    sentence = db.get(Sentence, payload.sentence_id)
    tile_set = db.get(SentenceTileSet, payload.tile_set_id)
    if sentence is None or tile_set is None:
        return {"kind": "broken_sentence_tiles", "error": "Broken sentence tile references"}
    tiles = list(
        db.scalars(select(SentenceTile).where(SentenceTile.tile_set_id == tile_set.id).order_by(SentenceTile.tile_index))
    )
    return {
        "kind": "sentence_tiles",
        "prompt": sentence.en_text if item.prompt_lang == "en" else sentence.ja_text,
        "answer_shape": f"{len(tiles)} ordered tiles in {item.answer_lang}",
        "correct_tiles": [tile.text for tile in tiles],
        "sentence": {"ja": sentence.ja_text, "en": sentence.en_text},
    }


def _summarize_kanji_kana_match(*, db: Session, item: Item) -> dict[str, object]:
    payload = db.get(ItemKanjiKanaMatch, item.id)
    if payload is None:
        return {"kind": "broken_kanji_kana_match", "error": "Missing item_kanji_kana_match payload"}
    word = db.get(Word, payload.word_id)
    if word is None:
        return {"kind": "broken_kanji_kana_match", "error": "Missing target word"}
    return {
        "kind": "kanji_kana_match",
        "prompt": word.canonical_writing_ja,
        "correct_answer": word.reading_kana,
        "target_word": {
            "canonical_writing_ja": word.canonical_writing_ja,
            "reading_kana": word.reading_kana,
            "gloss_primary_en": word.gloss_primary_en,
            "pos": word.pos,
        },
        "options_shape": "4 kana options",
    }


def _summarize_item(*, db: Session, item: Item) -> dict[str, object]:
    if item.type == "word_choice":
        summary = _summarize_word_choice(db=db, item=item)
    elif item.type == "sentence_tiles":
        summary = _summarize_sentence_tiles(db=db, item=item)
    elif item.type == "kanji_kana_match":
        summary = _summarize_kanji_kana_match(db=db, item=item)
    else:
        summary = {"kind": "unknown", "error": f"Unsupported item type: {item.type}"}
    return {
        "order_index": item.order_index,
        "type": item.type,
        "prompt_lang": item.prompt_lang,
        "answer_lang": item.answer_lang,
        **summary,
    }


def main() -> int:
    args = build_parser().parse_args()
    with SessionLocal() as db:
        section = db.scalar(
            select(Section).where(
                Section.course_version_id == args.course_version_id,
                Section.code == args.section_code,
            )
        )
        if section is None:
            raise SystemExit(
                f"Section not found for course_version_id={args.course_version_id} section_code={args.section_code}"
            )

        unit = db.scalar(
            select(Unit).where(Unit.section_id == section.id, Unit.order_index == args.unit_index)
        )
        if unit is None:
            raise SystemExit(
                f"Unit not found for course_version_id={args.course_version_id} "
                f"section_code={args.section_code} unit_index={args.unit_index}"
            )
        lesson = db.scalar(select(Lesson).where(Lesson.unit_id == unit.id, Lesson.order_index == args.lesson_index))
        if lesson is None:
            raise SystemExit(
                f"Lesson not found for course_version_id={args.course_version_id} "
                f"section_code={args.section_code} unit_index={args.unit_index} lesson_index={args.lesson_index}"
            )
        items = list(db.scalars(select(Item).where(Item.lesson_id == lesson.id).order_by(Item.order_index)))
        payload = {
            "course_version_id": args.course_version_id,
            "section_code": args.section_code,
            "section_title": section.title,
            "unit": {
                "order_index": unit.order_index,
                "title": unit.title,
                "description": unit.description,
            },
            "lesson": {
                "order_index": lesson.order_index,
                "kind": lesson.kind,
                "target_item_count": lesson.target_item_count,
                "items": [_summarize_item(db=db, item=item) for item in items],
            },
        }

    sys.stdout.write(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
