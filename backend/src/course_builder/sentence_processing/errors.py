from __future__ import annotations


class SentenceProcessingError(ValueError):
    pass


class UnsupportedSentenceStructureError(SentenceProcessingError):
    def __init__(
        self,
        *,
        sentence: str,
        normalized_sentence: str,
        failing_index: int,
        remaining_span: str,
        reason: str,
        parsed_prefix_surfaces: tuple[str, ...] = (),
        nearby_surfaces: tuple[str, ...] = (),
    ) -> None:
        parsed_prefix_suffix = (
            f" parsed_prefix_surfaces={list(parsed_prefix_surfaces)!r}" if parsed_prefix_surfaces else ""
        )
        nearby_surfaces_suffix = f" nearby_surfaces={list(nearby_surfaces)!r}" if nearby_surfaces else ""
        message = (
            "Unsupported sentence structure: "
            f"sentence={sentence!r} normalized_sentence={normalized_sentence!r} "
            f"failing_index={failing_index} remaining_span={remaining_span!r} "
            f"reason={reason}{parsed_prefix_suffix}{nearby_surfaces_suffix}"
        )
        super().__init__(message)


class UnsupportedChunkMergeError(SentenceProcessingError):
    def __init__(self, *, sentence: str, reason: str) -> None:
        super().__init__(f"Unsupported chunk merge: sentence={sentence!r} reason={reason}")
