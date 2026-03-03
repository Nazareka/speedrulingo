from __future__ import annotations

from course_builder.sentence_processing.errors import UnsupportedSentenceStructureError
from course_builder.sentence_processing.models import ParsedToken, SurfaceEntry, VocabItem
from course_builder.sentence_processing.surface_generation import generate_surface_entries


def build_surface_index(vocab: list[VocabItem]) -> dict[str, tuple[SurfaceEntry, ...]]:
    by_surface: dict[str, list[SurfaceEntry]] = {}
    for vocab_item in vocab:
        for entry in generate_surface_entries(vocab_item):
            by_surface.setdefault(entry.surface, []).append(entry)
    return {surface: tuple(entries) for surface, entries in by_surface.items()}


def _entry_score(entry: SurfaceEntry) -> int:
    score = len(entry.surface) * 100
    if entry.match_kind == "exact":
        score += 10_000
    else:
        score += 9_000
    if len(entry.vocab_items) == 1 and entry.vocab_items[0].pos == "expression":
        score += 1_000
    return score


def _find_nearby_surfaces(
    *,
    normalized_sentence: str,
    failing_index: int,
    surface_index: dict[str, tuple[SurfaceEntry, ...]],
) -> tuple[str, ...]:
    remaining_span = normalized_sentence[failing_index:]
    if not remaining_span:
        return ()
    ranked_surfaces = sorted(
        surface_index,
        key=lambda surface: (
            0 if remaining_span.startswith(surface[:1]) else 1,
            abs(len(surface) - len(remaining_span[: max(1, len(surface))])),
            surface,
        ),
    )
    return tuple(ranked_surfaces[:8])


def _find_furthest_parsed_prefix(
    *,
    normalized_sentence: str,
    surface_index: dict[str, tuple[SurfaceEntry, ...]],
) -> tuple[int, tuple[ParsedToken, ...]]:
    text_length = len(normalized_sentence)
    best_prefix: dict[int, tuple[int, tuple[ParsedToken, ...]]] = {0: (0, ())}

    for start_index in range(text_length):
        current_prefix = best_prefix.get(start_index)
        if current_prefix is None:
            continue
        for surface, entries in surface_index.items():
            if not normalized_sentence.startswith(surface, start_index):
                continue
            next_index = start_index + len(surface)
            for entry in entries:
                current_score = current_prefix[0] + _entry_score(entry)
                current_tokens = (
                    *current_prefix[1],
                    ParsedToken(
                        surface=entry.surface,
                        reading=entry.reading,
                        vocab_items=entry.vocab_items,
                        match_kind=entry.match_kind,
                    ),
                )
                existing_prefix = best_prefix.get(next_index)
                if existing_prefix is None or current_score > existing_prefix[0]:
                    best_prefix[next_index] = (current_score, current_tokens)

    furthest_index = max(best_prefix)
    return furthest_index, best_prefix[furthest_index][1]


def parse_sentence(
    *, original_sentence: str, normalized_sentence: str, surface_index: dict[str, tuple[SurfaceEntry, ...]]
) -> tuple[ParsedToken, ...]:
    text_length = len(normalized_sentence)
    best_suffix: dict[int, tuple[int, tuple[ParsedToken, ...]]] = {text_length: (0, ())}

    for start_index in range(text_length - 1, -1, -1):
        best_choice: tuple[int, tuple[ParsedToken, ...]] | None = None
        for surface, entries in surface_index.items():
            if not normalized_sentence.startswith(surface, start_index):
                continue
            next_index = start_index + len(surface)
            suffix = best_suffix.get(next_index)
            if suffix is None:
                continue
            for entry in entries:
                current_score = _entry_score(entry) + suffix[0]
                current_tokens = (
                    ParsedToken(
                        surface=entry.surface,
                        reading=entry.reading,
                        vocab_items=entry.vocab_items,
                        match_kind=entry.match_kind,
                    ),
                    *suffix[1],
                )
                if best_choice is None or current_score > best_choice[0]:
                    best_choice = (current_score, current_tokens)
        if best_choice is not None:
            best_suffix[start_index] = best_choice

    parsed = best_suffix.get(0)
    if parsed is None:
        furthest_reachable_index, prefix_tokens = _find_furthest_parsed_prefix(
            normalized_sentence=normalized_sentence,
            surface_index=surface_index,
        )
        raise UnsupportedSentenceStructureError(
            sentence=original_sentence,
            normalized_sentence=normalized_sentence,
            failing_index=furthest_reachable_index,
            remaining_span=normalized_sentence[furthest_reachable_index:],
            reason="no exact or generated vocab surface matched the remaining span",
            parsed_prefix_surfaces=tuple(token.surface for token in prefix_tokens),
            nearby_surfaces=_find_nearby_surfaces(
                normalized_sentence=normalized_sentence,
                failing_index=furthest_reachable_index,
                surface_index=surface_index,
            ),
        )
    return parsed[1]
