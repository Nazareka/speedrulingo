from __future__ import annotations

from course_builder.sentence_processing.hints import replace_chunk_hints
from course_builder.sentence_processing.models import HintChunk, ParsedToken


def _chunk_from_token(token: ParsedToken, *, token_index: int) -> HintChunk:
    return HintChunk(
        text=token.surface,
        token_start=token_index,
        token_end=token_index,
        vocab_items=token.vocab_items,
        hints=(),
        lemma=None,
        reading=token.reading,
        pos=None,
    )


def merge_hint_chunks(tokens: tuple[ParsedToken, ...]) -> tuple[HintChunk, ...]:
    return tuple(replace_chunk_hints(_chunk_from_token(token, token_index=index)) for index, token in enumerate(tokens))
