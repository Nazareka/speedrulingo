from __future__ import annotations

from course_builder.lexicon import is_kana_text
from course_builder.sentence_processing.models import SurfaceEntry, VocabItem

_I_ROW_BY_FINAL = {
    "う": "い",
    "く": "き",
    "ぐ": "ぎ",
    "す": "し",
    "つ": "ち",
    "ぬ": "に",
    "ぶ": "び",
    "む": "み",
    "る": "り",
}
_TE_FORM_BY_FINAL = {
    "う": "って",
    "つ": "って",
    "る": "って",
    "む": "んで",
    "ぶ": "んで",
    "ぬ": "んで",
    "く": "いて",
    "ぐ": "いで",
    "す": "して",
}
_I_E_ROW_KANA = {
    "い",
    "き",
    "ぎ",
    "し",
    "じ",
    "ち",
    "ぢ",
    "に",
    "ひ",
    "び",
    "ぴ",
    "み",
    "り",
    "え",
    "け",
    "げ",
    "せ",
    "ぜ",
    "て",
    "で",
    "ね",
    "へ",
    "べ",
    "ぺ",
    "め",
    "れ",
}
_GODAN_RU_EXCEPTIONS = frozenset(
    {
        "かえる",
        "はしる",
        "はいる",
    }
)
MIN_RU_VERB_READING_LENGTH = 2


def _is_ru_verb(reading_kana: str) -> bool:
    if len(reading_kana) < MIN_RU_VERB_READING_LENGTH or not reading_kana.endswith("る"):
        return False
    if reading_kana in _GODAN_RU_EXCEPTIONS:
        return False
    return reading_kana[-2] in _I_E_ROW_KANA


def _infer_verb_class(vocab_item: VocabItem) -> str:
    reading = vocab_item.reading_kana
    canonical = vocab_item.canonical_writing_ja
    if reading.endswith("する"):
        return "suru"
    if reading == "くる" or canonical in {"来る", "くる"}:
        return "kuru"
    if _is_ru_verb(reading):
        return "ru"
    return "u"


def _generated_surface_reading_pairs_for_base(
    surface: str,
    *,
    reading: str,
    verb_class: str,
) -> tuple[tuple[str, str], ...]:
    if verb_class == "suru":
        if surface == "する":
            stem = "し"
            return (
                (stem, stem),
                ("して", "して"),
                ("します", "します"),
                ("しません", "しません"),
                ("しました", "しました"),
                ("しませんでした", "しませんでした"),
                ("しませんか", "しませんか"),
                ("している", "している"),
                ("しています", "しています"),
            )
        stem = surface.removesuffix("する")
        reading_stem = reading.removesuffix("する")
        return (
            (stem, reading_stem),
            (f"{stem}し", f"{reading_stem}し"),
            (f"{stem}して", f"{reading_stem}して"),
            (f"{stem}します", f"{reading_stem}します"),
            (f"{stem}しません", f"{reading_stem}しません"),
            (f"{stem}しました", f"{reading_stem}しました"),
            (f"{stem}しませんでした", f"{reading_stem}しませんでした"),
            (f"{stem}しませんか", f"{reading_stem}しませんか"),
            (f"{stem}している", f"{reading_stem}している"),
            (f"{stem}しています", f"{reading_stem}しています"),
        )
    if verb_class == "kuru":
        stem = surface[:-2]
        if surface == reading:
            polite_stem = f"{stem}き"
            return (
                (polite_stem, polite_stem),
                (f"{polite_stem}て", f"{polite_stem}て"),
                (f"{polite_stem}ます", f"{polite_stem}ます"),
                (f"{polite_stem}ません", f"{polite_stem}ません"),
                (f"{polite_stem}ました", f"{polite_stem}ました"),
                (f"{polite_stem}ませんでした", f"{polite_stem}ませんでした"),
                (f"{polite_stem}ませんか", f"{polite_stem}ませんか"),
                (f"{polite_stem}ている", f"{polite_stem}ている"),
                (f"{polite_stem}ています", f"{polite_stem}ています"),
            )
        polite_stem = "来" if surface == "来る" else stem
        polite_reading_stem = "き"
        return (
            (polite_stem, polite_reading_stem),
            ("来て" if surface == "来る" else f"{polite_stem}て", f"{polite_reading_stem}て"),
            (f"{polite_stem}ます", f"{polite_reading_stem}ます"),
            (f"{polite_stem}ません", f"{polite_reading_stem}ません"),
            (f"{polite_stem}ました", f"{polite_reading_stem}ました"),
            (f"{polite_stem}ませんでした", f"{polite_reading_stem}ませんでした"),
            (f"{polite_stem}ませんか", f"{polite_reading_stem}ませんか"),
            (f"{polite_stem}ている", f"{polite_reading_stem}ている"),
            (f"{polite_stem}ています", f"{polite_reading_stem}ています"),
        )
    if verb_class == "ru":
        stem = surface[:-1]
        reading_stem = reading[:-1]
        return (
            (stem, reading_stem),
            (f"{stem}て", f"{reading_stem}て"),
            (f"{stem}ます", f"{reading_stem}ます"),
            (f"{stem}ません", f"{reading_stem}ません"),
            (f"{stem}ました", f"{reading_stem}ました"),
            (f"{stem}ませんでした", f"{reading_stem}ませんでした"),
            (f"{stem}ませんか", f"{reading_stem}ませんか"),
            (f"{stem}ている", f"{reading_stem}ている"),
            (f"{stem}ています", f"{reading_stem}ています"),
        )

    final = reading[-1]
    polite = _I_ROW_BY_FINAL.get(final)
    te_form = _TE_FORM_BY_FINAL.get(final)
    if polite is None or te_form is None:
        return ()
    plain_stem = surface[:-1]
    reading_stem = reading[:-1]
    polite_stem = f"{plain_stem}{polite}"
    polite_reading_stem = f"{reading_stem}{polite}"
    te_stem = f"{plain_stem}{te_form}"
    te_reading_stem = f"{reading_stem}{te_form}"
    return (
        (polite_stem, polite_reading_stem),
        (te_stem, te_reading_stem),
        (f"{polite_stem}ます", f"{polite_reading_stem}ます"),
        (f"{polite_stem}ません", f"{polite_reading_stem}ません"),
        (f"{polite_stem}ました", f"{polite_reading_stem}ました"),
        (f"{polite_stem}ませんでした", f"{polite_reading_stem}ませんでした"),
        (f"{polite_stem}ませんか", f"{polite_reading_stem}ませんか"),
        (f"{te_stem}いる", f"{te_reading_stem}いる"),
        (f"{te_stem}います", f"{te_reading_stem}います"),
    )


def _generated_i_adjective_surface_reading_pairs_for_base(
    surface: str,
    *,
    reading: str,
) -> tuple[tuple[str, str], ...]:
    if not surface.endswith("い"):
        return ()
    stem = surface[:-1]
    reading_stem = reading[:-1]
    return (
        (f"{stem}くない", f"{reading_stem}くない"),
        (f"{stem}くないです", f"{reading_stem}くないです"),
        (f"{stem}かった", f"{reading_stem}かった"),
        (f"{stem}かったです", f"{reading_stem}かったです"),
        (f"{stem}くなかった", f"{reading_stem}くなかった"),
        (f"{stem}くなかったです", f"{reading_stem}くなかったです"),
    )


def generate_surface_entries(vocab_item: VocabItem) -> tuple[SurfaceEntry, ...]:
    entries: list[SurfaceEntry] = [
        SurfaceEntry(
            surface=vocab_item.canonical_writing_ja,
            reading=vocab_item.reading_kana,
            vocab_items=(vocab_item,),
            match_kind="exact",
        ),
    ]
    if vocab_item.reading_kana != vocab_item.canonical_writing_ja:
        entries.append(
            SurfaceEntry(
                surface=vocab_item.reading_kana,
                reading=vocab_item.reading_kana,
                vocab_items=(vocab_item,),
                match_kind="exact",
            )
        )

    if vocab_item.pos == "adjective_i":
        seen_surfaces = {entry.surface for entry in entries}
        base_surfaces = [vocab_item.canonical_writing_ja]
        if is_kana_text(vocab_item.reading_kana) and vocab_item.reading_kana != vocab_item.canonical_writing_ja:
            base_surfaces.append(vocab_item.reading_kana)
        for base_surface in base_surfaces:
            for generated_surface, generated_reading in _generated_i_adjective_surface_reading_pairs_for_base(
                base_surface,
                reading=vocab_item.reading_kana,
            ):
                if generated_surface in seen_surfaces:
                    continue
                seen_surfaces.add(generated_surface)
                entries.append(
                    SurfaceEntry(
                        surface=generated_surface,
                        reading=generated_reading,
                        vocab_items=(vocab_item,),
                        match_kind="generated",
                    )
                )
        return tuple(entries)

    if vocab_item.pos != "verb":
        return tuple(entries)

    verb_class = _infer_verb_class(vocab_item)
    seen_surfaces = {entry.surface for entry in entries}
    base_surfaces = [vocab_item.canonical_writing_ja]
    if is_kana_text(vocab_item.reading_kana) and vocab_item.reading_kana != vocab_item.canonical_writing_ja:
        base_surfaces.append(vocab_item.reading_kana)
    for base_surface in base_surfaces:
        for generated_surface, generated_reading in _generated_surface_reading_pairs_for_base(
            base_surface,
            reading=vocab_item.reading_kana,
            verb_class=verb_class,
        ):
            if generated_surface in seen_surfaces:
                continue
            seen_surfaces.add(generated_surface)
            entries.append(
                SurfaceEntry(
                    surface=generated_surface,
                    reading=generated_reading,
                    vocab_items=(vocab_item,),
                    match_kind="generated",
                )
            )
    return tuple(entries)
