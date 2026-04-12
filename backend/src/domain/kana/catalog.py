from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.kana.models import KanaCharacter

TARGET_EXPOSURES = 6


@dataclass(frozen=True, slots=True)
class KanaSeed:
    char: str
    script: str
    sound_text: str
    group_key: str
    group_order: int
    difficulty_rank: int
    base_char: str | None = None
    is_voiced: bool = False


def _build_catalog() -> list[KanaSeed]:
    seeds: list[KanaSeed] = []

    def add_pair_group(
        *,
        group_key: str,
        group_order: int,
        hiragana: str,
        katakana: str,
        sounds: tuple[str, ...],
    ) -> None:
        for index, (hiragana_char, katakana_char, sound) in enumerate(zip(hiragana, katakana, sounds, strict=True)):
            rank = group_order * 10 + index
            seeds.append(
                KanaSeed(
                    char=hiragana_char,
                    script="hiragana",
                    sound_text=sound,
                    group_key=group_key,
                    group_order=group_order,
                    difficulty_rank=rank,
                )
            )
            seeds.append(
                KanaSeed(
                    char=katakana_char,
                    script="katakana",
                    sound_text=sound,
                    group_key=group_key,
                    group_order=group_order + 20,
                    difficulty_rank=rank + 200,
                )
            )

    add_pair_group(group_key="vowels", group_order=1, hiragana="あいうえお", katakana="アイウエオ", sounds=("あ", "い", "う", "え", "お"))
    add_pair_group(group_key="k", group_order=2, hiragana="かきくけこ", katakana="カキクケコ", sounds=("か", "き", "く", "け", "こ"))
    add_pair_group(group_key="s", group_order=3, hiragana="さしすせそ", katakana="サシスセソ", sounds=("さ", "し", "す", "せ", "そ"))
    add_pair_group(group_key="t", group_order=4, hiragana="たちつてと", katakana="タチツテト", sounds=("た", "ち", "つ", "て", "と"))
    add_pair_group(group_key="n", group_order=5, hiragana="なにぬねの", katakana="ナニヌネノ", sounds=("な", "に", "ぬ", "ね", "の"))
    add_pair_group(group_key="h", group_order=6, hiragana="はひふへほ", katakana="ハヒフヘホ", sounds=("は", "ひ", "ふ", "へ", "ほ"))
    add_pair_group(group_key="m", group_order=7, hiragana="まみむめも", katakana="マミムメモ", sounds=("ま", "み", "む", "め", "も"))
    add_pair_group(group_key="y", group_order=8, hiragana="やゆよ", katakana="ヤユヨ", sounds=("や", "ゆ", "よ"))
    add_pair_group(group_key="r", group_order=9, hiragana="らりるれろ", katakana="ラリルレロ", sounds=("ら", "り", "る", "れ", "ろ"))
    add_pair_group(group_key="w", group_order=10, hiragana="わをん", katakana="ワヲン", sounds=("わ", "を", "ん"))
    add_pair_group(group_key="g", group_order=11, hiragana="がぎぐげご", katakana="ガギグゲゴ", sounds=("が", "ぎ", "ぐ", "げ", "ご"))
    add_pair_group(group_key="z", group_order=12, hiragana="ざじずぜぞ", katakana="ザジズゼゾ", sounds=("ざ", "じ", "ず", "ぜ", "ぞ"))
    add_pair_group(group_key="d", group_order=13, hiragana="だぢづでど", katakana="ダヂヅデド", sounds=("だ", "ぢ", "づ", "で", "ど"))
    add_pair_group(group_key="b", group_order=14, hiragana="ばびぶべぼ", katakana="バビブベボ", sounds=("ば", "び", "ぶ", "べ", "ぼ"))
    add_pair_group(group_key="p", group_order=15, hiragana="ぱぴぷぺぽ", katakana="パピプペポ", sounds=("ぱ", "ぴ", "ぷ", "ぺ", "ぽ"))

    seeds.append(
        KanaSeed(
            char="ゔ",
            script="hiragana",
            sound_text="ゔ",
            group_key="vu",
            group_order=17,
            difficulty_rank=172,
            base_char="う",
            is_voiced=True,
        )
    )
    seeds.append(
        KanaSeed(
            char="ヴ",
            script="katakana",
            sound_text="ゔ",
            group_key="vu",
            group_order=37,
            difficulty_rank=372,
            base_char="ウ",
            is_voiced=True,
        )
    )

    base_map = {
        "が": "か",
        "ぎ": "き",
        "ぐ": "く",
        "げ": "け",
        "ご": "こ",
        "ざ": "さ",
        "じ": "し",
        "ず": "す",
        "ぜ": "せ",
        "ぞ": "そ",
        "だ": "た",
        "ぢ": "ち",
        "づ": "つ",
        "で": "て",
        "ど": "と",
        "ば": "は",
        "び": "ひ",
        "ぶ": "ふ",
        "べ": "へ",
        "ぼ": "ほ",
        "ぱ": "は",
        "ぴ": "ひ",
        "ぷ": "ふ",
        "ぺ": "へ",
        "ぽ": "ほ",
    }
    kata_map = str.maketrans(
        "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ",
        "かきくけこさしすせそたちつてとはひふへほはひふへほ",
    )
    for index, seed in enumerate(seeds):
        if seed.base_char is not None:
            continue
        if seed.char in base_map:
            seeds[index] = KanaSeed(
                char=seed.char,
                script=seed.script,
                sound_text=seed.sound_text,
                group_key=seed.group_key,
                group_order=seed.group_order,
                difficulty_rank=seed.difficulty_rank,
                base_char=base_map[seed.char],
                is_voiced=True,
            )
        elif seed.script == "katakana" and seed.char.translate(kata_map) != seed.char:
            seeds[index] = KanaSeed(
                char=seed.char,
                script=seed.script,
                sound_text=seed.sound_text,
                group_key=seed.group_key,
                group_order=seed.group_order,
                difficulty_rank=seed.difficulty_rank,
                base_char=seed.char.translate(kata_map),
                is_voiced=True,
            )
    return seeds


CATALOG = tuple(_build_catalog())


def ensure_kana_catalog_seeded(db: Session) -> None:
    existing_chars = set(db.scalars(select(KanaCharacter.char)))
    if len(existing_chars) >= len(CATALOG):
        return

    for seed in CATALOG:
        if seed.char in existing_chars:
            continue
        db.add(
            KanaCharacter(
                char=seed.char,
                script=seed.script,
                sound_text=seed.sound_text,
                group_key=seed.group_key,
                group_order=seed.group_order,
                difficulty_rank=seed.difficulty_rank,
                target_exposures=TARGET_EXPOSURES,
                base_char=seed.base_char,
                is_voiced=seed.is_voiced,
            )
        )
    db.flush()
