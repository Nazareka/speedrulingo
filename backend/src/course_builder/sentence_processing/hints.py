from __future__ import annotations

from course_builder.sentence_processing.models import HintChunk, VocabItem

MAX_HINTS_PER_CHUNK = 3


def _normalized_hint_key(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def build_chunk_hints(vocab_items: tuple[VocabItem, ...]) -> tuple[str, ...]:
    ordered_candidates: list[str] = []
    for vocab_item in vocab_items:
        if vocab_item.gloss_primary_en.strip():
            ordered_candidates.append(vocab_item.gloss_primary_en.strip())
        ordered_candidates.extend(gloss.strip() for gloss in vocab_item.gloss_alternatives_en if gloss.strip())
    deduped: list[str] = []
    seen_keys: set[str] = set()
    for candidate in ordered_candidates:
        normalized_key = _normalized_hint_key(candidate)
        if not normalized_key or normalized_key in seen_keys:
            continue
        seen_keys.add(normalized_key)
        deduped.append(candidate)
        if len(deduped) == MAX_HINTS_PER_CHUNK:
            break
    return tuple(deduped)


def chunk_reading(vocab_items: tuple[VocabItem, ...]) -> str | None:
    readings = [item.reading_kana for item in vocab_items if item.reading_kana]
    if not readings:
        return None
    return "".join(readings)


def chunk_lemma(vocab_items: tuple[VocabItem, ...]) -> str | None:
    lemmas = [item.canonical_writing_ja for item in vocab_items if item.canonical_writing_ja]
    if not lemmas:
        return None
    if len(lemmas) == 1:
        return lemmas[0]
    return "".join(lemmas)


def chunk_pos(vocab_items: tuple[VocabItem, ...]) -> str | None:
    return vocab_items[0].pos if vocab_items else None


def replace_chunk_hints(chunk: HintChunk) -> HintChunk:
    return HintChunk(
        text=chunk.text,
        token_start=chunk.token_start,
        token_end=chunk.token_end,
        vocab_items=chunk.vocab_items,
        hints=build_chunk_hints(chunk.vocab_items),
        lemma=chunk_lemma(chunk.vocab_items),
        reading=chunk.reading if chunk.reading is not None else chunk_reading(chunk.vocab_items),
        pos=chunk_pos(chunk.vocab_items),
    )
