from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from course_builder.queries.assembly import AssemblyQueries
from course_builder.runtime.models import BuildContext
from course_builder.sentence_processing.normalization import strip_english_for_tiles, strip_japanese_for_matching
from domain.content.models import ItemSentenceTiles, SentenceTile, SentenceTileSet, SentenceUnit


@dataclass(frozen=True, slots=True)
class TileSpec:
    text: str
    unit_start: int
    unit_end: int


@dataclass(frozen=True, slots=True)
class TileGenerationStats:
    tile_sets_created: int
    tiles_created: int


def _build_tiles(tokens: list[SentenceUnit]) -> list[TileSpec]:
    tile_specs: list[TileSpec] = []
    for token in tokens:
        surface = token.surface.strip()
        if not surface:
            continue
        tile_specs.append(
            TileSpec(
                text=surface,
                unit_start=token.unit_index,
                unit_end=token.unit_index,
            )
        )
    return tile_specs


def _build_english_tiles(tokens: list[SentenceUnit]) -> list[TileSpec]:
    tile_specs: list[TileSpec] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        surface = token.surface.strip()
        if not surface:
            index += 1
            continue
        if len(surface) == 1 and surface.isalpha():
            end_index = index
            merged_surface = surface
            while end_index + 1 < len(tokens):
                next_surface = tokens[end_index + 1].surface.strip()
                if len(next_surface) != 1 or not next_surface.isalpha():
                    break
                merged_surface += next_surface
                end_index += 1
            if end_index > index:
                tile_specs.append(
                    TileSpec(
                        text=merged_surface,
                        unit_start=tokens[index].unit_index,
                        unit_end=tokens[end_index].unit_index,
                    )
                )
                index = end_index + 1
                continue
        tile_specs.append(
            TileSpec(
                text=surface,
                unit_start=token.unit_index,
                unit_end=token.unit_index,
            )
        )
        index += 1
    return tile_specs


def _validate_tile_specs(tile_specs: list[TileSpec], *, original_text: str, answer_lang: str) -> None:
    if not tile_specs:
        raise ValueError("Tile generation must produce at least one tile")
    if any(not tile_spec.text.strip() for tile_spec in tile_specs):
        raise ValueError("Tile generation must not produce empty tiles")
    if answer_lang == "ja":
        original_text = strip_japanese_for_matching(original_text)
        reconstructed_text = "".join(tile_spec.text for tile_spec in tile_specs)
    else:
        original_text = strip_english_for_tiles(original_text)
        reconstructed_text = " ".join(tile_spec.text for tile_spec in tile_specs).strip()
    if reconstructed_text != original_text:
        msg = f"Tile generation failed to reconstruct original text: {reconstructed_text!r} != {original_text!r}"
        raise ValueError(msg)


def build_tile_sets(
    db: Session,
    *,
    context: BuildContext,
) -> TileGenerationStats:
    q = AssemblyQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = f"Section config must exist before tile generation for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    sentence_ids = q.list_section_sentence_ids(section_id=section.id)
    if not sentence_ids:
        return TileGenerationStats(tile_sets_created=0, tiles_created=0)

    existing_tile_set_ids = q.list_tile_set_ids_for_sentences(sentence_ids=sentence_ids)
    if existing_tile_set_ids:
        db.execute(delete(ItemSentenceTiles).where(ItemSentenceTiles.tile_set_id.in_(existing_tile_set_ids)))
        db.execute(delete(SentenceTile).where(SentenceTile.tile_set_id.in_(existing_tile_set_ids)))
        db.execute(delete(SentenceTileSet).where(SentenceTileSet.id.in_(existing_tile_set_ids)))

    sentence_text_by_id = q.map_sentence_texts_by_id(sentence_ids=sentence_ids)
    unit_rows = q.list_sentence_units(sentence_ids=sentence_ids)
    units_by_sentence_lang: dict[tuple[str, str], list[SentenceUnit]] = {}
    for unit in unit_rows:
        units_by_sentence_lang.setdefault((unit.sentence_id, unit.lang), []).append(unit)

    tile_sets_created = 0
    tiles_created = 0
    for sentence_id in sentence_ids:
        for answer_lang in ("ja", "en"):
            source_units = units_by_sentence_lang.get((sentence_id, answer_lang), [])
            if not source_units:
                continue
            tile_set = SentenceTileSet(
                sentence_id=sentence_id,
                answer_lang=answer_lang,
            )
            db.add(tile_set)
            db.flush()
            tile_sets_created += 1

            tile_specs = _build_english_tiles(source_units) if answer_lang == "en" else _build_tiles(source_units)

            _validate_tile_specs(
                tile_specs,
                original_text=sentence_text_by_id[sentence_id][answer_lang],
                answer_lang=answer_lang,
            )
            for tile_index, tile_spec in enumerate(tile_specs):
                db.add(
                    SentenceTile(
                        tile_set_id=tile_set.id,
                        tile_index=tile_index,
                        text=tile_spec.text,
                        unit_start=tile_spec.unit_start,
                        unit_end=tile_spec.unit_end,
                    )
                )
                tiles_created += 1

    db.commit()
    return TileGenerationStats(tile_sets_created=tile_sets_created, tiles_created=tiles_created)
