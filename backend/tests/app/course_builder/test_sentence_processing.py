from __future__ import annotations

import pytest

from course_builder.sentence_processing import (
    VocabItem,
    build_japanese_sentence_analysis,
    normalize_sentence_texts,
    tokenize_english_sentence,
)
from course_builder.sentence_processing.errors import UnsupportedSentenceStructureError


def _vocab_item(
    canonical_writing_ja: str,
    reading_kana: str,
    *,
    pos: str,
    gloss_primary_en: str,
    gloss_alternatives_en: tuple[str, ...] = (),
) -> VocabItem:
    return VocabItem(
        word_id=None,
        canonical_writing_ja=canonical_writing_ja,
        reading_kana=reading_kana,
        gloss_primary_en=gloss_primary_en,
        gloss_alternatives_en=gloss_alternatives_en,
        usage_note_en=None,
        pos=pos,
    )


def test_normalize_sentence_texts_removes_only_trailing_terminal_punctuation() -> None:
    normalized_ja, normalized_en = normalize_sentence_texts(
        ja_text="これはペンです。 それは本です。",
        en_text="This is a pen. That is a book.",
    )

    assert normalized_ja == "これはペンです。それは本です"
    assert normalized_en == "This is a pen. That is a book"


def test_build_japanese_sentence_analysis_keeps_each_token_as_separate_chunk() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="山田さんのかばんです。",
        vocab=[
            _vocab_item("山田", "やまだ", pos="proper_noun", gloss_primary_en="Yamada"),
            _vocab_item("さん", "さん", pos="suffix", gloss_primary_en="Mr./Ms."),
            _vocab_item(
                "の", "の", pos="particle", gloss_primary_en="linker, of", gloss_alternatives_en=("possessive linker",)
            ),
            _vocab_item("かばん", "かばん", pos="noun", gloss_primary_en="bag"),
            _vocab_item("です", "です", pos="copula", gloss_primary_en="is"),
        ],
    )

    assert result.normalized_sentence == "山田さんのかばんです"
    assert [chunk.text for chunk in result.chunks] == ["山田", "さん", "の", "かばん", "です"]
    assert result.chunks[0].hints == ("Yamada",)
    assert result.chunks[1].hints == ("Mr./Ms.",)
    assert result.chunks[2].hints == ("linker, of", "possessive linker")


def test_build_japanese_sentence_analysis_supports_generated_polite_verb_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="私は日本語を勉強します。",
        vocab=[
            _vocab_item("私", "わたし", pos="pronoun", gloss_primary_en="I"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("日本語", "にほんご", pos="noun", gloss_primary_en="Japanese"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("勉強する", "べんきょうする", pos="verb", gloss_primary_en="study"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["私", "は", "日本語", "を", "勉強します"]
    assert result.tokens[-1].match_kind == "generated"
    assert result.chunks[-1].hints == ("study",)


def test_build_japanese_sentence_analysis_supports_generated_te_imasu_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="私は東京に住んでいます。",
        vocab=[
            _vocab_item("私", "わたし", pos="pronoun", gloss_primary_en="I"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("東京", "とうきょう", pos="noun", gloss_primary_en="Tokyo"),
            _vocab_item("に", "に", pos="particle", gloss_primary_en="in"),
            _vocab_item("住む", "すむ", pos="verb", gloss_primary_en="live"),
        ],
    )

    assert result.tokens[-1].surface == "住んでいます"
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_generated_suru_masu_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="ケンさんはサッカーをします。",
        vocab=[
            _vocab_item("ケン", "けん", pos="proper_noun", gloss_primary_en="Ken"),
            _vocab_item("さん", "さん", pos="suffix", gloss_primary_en="Mr./Ms."),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("サッカー", "さっかー", pos="noun", gloss_primary_en="soccer"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("する", "する", pos="verb", gloss_primary_en="do"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["ケン", "さん", "は", "サッカー", "を", "します"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_suru_compound_nominal_stem_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="勉強は大変です。",
        vocab=[
            _vocab_item("勉強する", "べんきょうする", pos="verb", gloss_primary_en="study"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("大変", "たいへん", pos="adjective_na", gloss_primary_en="difficult"),
            _vocab_item("です", "です", pos="copula", gloss_primary_en="is"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["勉強", "は", "大変", "です"]
    assert result.tokens[0].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_generated_polite_negative_invitation_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="映画を見ませんか。",
        vocab=[
            _vocab_item("映画", "えいが", pos="noun", gloss_primary_en="movie"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("見る", "みる", pos="verb", gloss_primary_en="watch"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["映画", "を", "見ませんか"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_generated_polite_past_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="昨日映画を見ました。",
        vocab=[
            _vocab_item("昨日", "きのう", pos="noun", gloss_primary_en="yesterday"),
            _vocab_item("映画", "えいが", pos="noun", gloss_primary_en="movie"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("見る", "みる", pos="verb", gloss_primary_en="watch"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["昨日", "映画", "を", "見ました"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_generated_polite_past_negative_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="昨日は行きませんでした。",
        vocab=[
            _vocab_item("昨日", "きのう", pos="noun", gloss_primary_en="yesterday"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("行く", "いく", pos="verb", gloss_primary_en="go"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["昨日", "は", "行きませんでした"]
    assert result.tokens[-1].match_kind == "generated"
    assert result.tokens[-1].reading == "いきませんでした"


def test_build_japanese_sentence_analysis_supports_generated_verb_stem_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="映画を見に行きます。",
        vocab=[
            _vocab_item("映画", "えいが", pos="noun", gloss_primary_en="movie"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("見る", "みる", pos="verb", gloss_primary_en="watch"),
            _vocab_item("に", "に", pos="particle", gloss_primary_en="for"),
            _vocab_item("行く", "いく", pos="verb", gloss_primary_en="go"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["映画", "を", "見", "に", "行きます"]
    assert result.tokens[2].match_kind == "generated"
    assert result.tokens[2].reading == "み"
    assert result.tokens[-1].reading == "いきます"


def test_build_japanese_sentence_analysis_supports_godan_ru_exception_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="うちに帰ります。",
        vocab=[
            _vocab_item("うち", "うち", pos="noun", gloss_primary_en="home"),
            _vocab_item("に", "に", pos="particle", gloss_primary_en="to"),
            _vocab_item("帰る", "かえる", pos="verb", gloss_primary_en="return"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["うち", "に", "帰ります"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_hashiru_godan_ru_exception_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="公園で走ります。",
        vocab=[
            _vocab_item("公園", "こうえん", pos="noun", gloss_primary_en="park"),
            _vocab_item("で", "で", pos="particle", gloss_primary_en="at"),
            _vocab_item("走る", "はしる", pos="verb", gloss_primary_en="run"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["公園", "で", "走ります"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_kuru_kanji_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="東京に来ます。",
        vocab=[
            _vocab_item("東京", "とうきょう", pos="noun", gloss_primary_en="Tokyo"),
            _vocab_item("に", "に", pos="particle", gloss_primary_en="to"),
            _vocab_item("来る", "くる", pos="verb", gloss_primary_en="come"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["東京", "に", "来ます"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_godan_ku_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="うちでコーヒーを作ります。",
        vocab=[
            _vocab_item("うち", "うち", pos="noun", gloss_primary_en="home"),
            _vocab_item("で", "で", pos="particle", gloss_primary_en="at"),
            _vocab_item("コーヒー", "こーひー", pos="noun", gloss_primary_en="coffee"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("作る", "つくる", pos="verb", gloss_primary_en="make"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["うち", "で", "コーヒー", "を", "作ります"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_godan_ku_polite_past_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="昨日、ケーキを作りました。",
        vocab=[
            _vocab_item("昨日", "きのう", pos="noun", gloss_primary_en="yesterday"),
            _vocab_item("ケーキ", "けーき", pos="noun", gloss_primary_en="cake"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("作る", "つくる", pos="verb", gloss_primary_en="make"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["昨日", "ケーキ", "を", "作りました"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_bare_te_form_clause_chaining() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="ここで待って、コーヒーを飲みます。",
        vocab=[
            _vocab_item("ここ", "ここ", pos="pronoun", gloss_primary_en="here"),
            _vocab_item("で", "で", pos="particle", gloss_primary_en="at"),
            _vocab_item("待つ", "まつ", pos="verb", gloss_primary_en="wait"),
            _vocab_item("コーヒー", "こーひー", pos="noun", gloss_primary_en="coffee"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("飲む", "のむ", pos="verb", gloss_primary_en="drink"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["ここ", "で", "待って", "コーヒー", "を", "飲みます"]
    assert result.tokens[2].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_bare_te_form_for_u_verb() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="ペンを使って、書きます。",
        vocab=[
            _vocab_item("ペン", "ぺん", pos="noun", gloss_primary_en="pen"),
            _vocab_item("を", "を", pos="particle", gloss_primary_en="object particle"),
            _vocab_item("使う", "つかう", pos="verb", gloss_primary_en="use"),
            _vocab_item("書く", "かく", pos="verb", gloss_primary_en="write"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["ペン", "を", "使って", "書きます"]
    assert result.tokens[2].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_godan_ru_exception_te_form_with_mo_ii_desu_ka() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="トイレに入ってもいいですか。",
        vocab=[
            _vocab_item("トイレ", "といれ", pos="noun", gloss_primary_en="toilet"),
            _vocab_item("に", "に", pos="particle", gloss_primary_en="to"),
            _vocab_item("入る", "はいる", pos="verb", gloss_primary_en="enter"),
            _vocab_item("も", "も", pos="particle", gloss_primary_en="also"),
            _vocab_item("いい", "いい", pos="adjective_i", gloss_primary_en="good"),
            _vocab_item("です", "です", pos="copula", gloss_primary_en="is"),
            _vocab_item("か", "か", pos="particle", gloss_primary_en="question particle"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["トイレ", "に", "入って", "も", "いい", "です", "か"]
    assert result.tokens[2].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_godan_ru_exception_te_form_with_wa_ikemasen() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="ここに入ってはいけません。",
        vocab=[
            _vocab_item("ここ", "ここ", pos="pronoun", gloss_primary_en="here"),
            _vocab_item("に", "に", pos="particle", gloss_primary_en="to"),
            _vocab_item("入る", "はいる", pos="verb", gloss_primary_en="enter"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("いけません", "いけません", pos="expression", gloss_primary_en="must not"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["ここ", "に", "入って", "は", "いけません"]
    assert result.tokens[2].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_i_adjective_negative_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="この本は高くないです。",
        vocab=[
            _vocab_item("この", "この", pos="pronoun", gloss_primary_en="this"),
            _vocab_item("本", "ほん", pos="noun", gloss_primary_en="book"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("高い", "たかい", pos="adjective_i", gloss_primary_en="expensive, tall"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["この", "本", "は", "高くないです"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_i_adjective_past_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="映画は面白かったです。",
        vocab=[
            _vocab_item("映画", "えいが", pos="noun", gloss_primary_en="movie"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("面白い", "おもしろい", pos="adjective_i", gloss_primary_en="interesting"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["映画", "は", "面白かったです"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_supports_i_adjective_negative_past_polite_surface() -> None:
    result = build_japanese_sentence_analysis(
        sentence_ja="昨日は寒くなかったです。",
        vocab=[
            _vocab_item("昨日", "きのう", pos="noun", gloss_primary_en="yesterday"),
            _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
            _vocab_item("寒い", "さむい", pos="adjective_i", gloss_primary_en="cold"),
        ],
    )

    assert [token.surface for token in result.tokens] == ["昨日", "は", "寒くなかったです"]
    assert result.tokens[-1].match_kind == "generated"


def test_build_japanese_sentence_analysis_raises_on_unsupported_structure() -> None:
    with pytest.raises(
        UnsupportedSentenceStructureError,
        match=r"failing_index=5 remaining_span='行った'.*parsed_prefix_surfaces=\['私', 'は', '東京', 'へ'\].*nearby_surfaces=",
    ):
        build_japanese_sentence_analysis(
            sentence_ja="私は東京へ行った。",
            vocab=[
                _vocab_item("私", "わたし", pos="pronoun", gloss_primary_en="I"),
                _vocab_item("は", "は", pos="particle", gloss_primary_en="topic particle"),
                _vocab_item("東京", "とうきょう", pos="noun", gloss_primary_en="Tokyo"),
                _vocab_item("へ", "へ", pos="particle", gloss_primary_en="to"),
                _vocab_item("行く", "いく", pos="verb", gloss_primary_en="go"),
            ],
        )


def test_tokenize_english_sentence_strips_punctuation_from_tiles() -> None:
    tokens = tokenize_english_sentence('This is "you\'re welcome."')

    assert [token.surface for token in tokens] == ["This", "is", "you're", "welcome"]


def test_tokenize_english_sentence_normalizes_dotted_abbreviations() -> None:
    tokens = tokenize_english_sentence("I go home at 3 p.m.")

    assert [token.surface for token in tokens] == ["I", "go", "home", "at", "3", "pm"]


def test_tokenize_english_sentence_keeps_compound_numbers_as_one_tile_token() -> None:
    tokens = tokenize_english_sentence("I wake up at 8:20.")

    assert [token.surface for token in tokens] == ["I", "wake", "up", "at", "820"]
