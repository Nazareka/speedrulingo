from course_builder.lexicon import LexemePos, is_hiragana, is_kanji
from course_builder.llm.pattern_vocab_generation.json_schema import WordBatchItemPayload


def _sentence_uses_i_adjective_lemma(*, lemma: str, sentence_ja_text: str) -> bool:
    if not lemma.endswith("い"):
        return False
    stem = lemma[:-1]
    supported_surfaces = (
        lemma,
        f"{stem}くない",
        f"{stem}くないです",
        f"{stem}かった",
        f"{stem}かったです",
        f"{stem}くなかった",
        f"{stem}くなかったです",
    )
    return any(surface in sentence_ja_text for surface in supported_surfaces)


def sentence_uses_generated_lemma(*, candidate: WordBatchItemPayload, sentence_ja_text: str) -> bool:
    if candidate.canonical_writing_ja in sentence_ja_text:
        return True
    if candidate.pos == LexemePos.ADJECTIVE_I:
        return _sentence_uses_i_adjective_lemma(lemma=candidate.canonical_writing_ja, sentence_ja_text=sentence_ja_text)
    if candidate.pos != LexemePos.VERB:
        return False
    lemma = candidate.canonical_writing_ja
    if not lemma:
        return False
    first_character = lemma[0]
    if is_hiragana(first_character):
        return first_character in sentence_ja_text
    kanji_characters = [character for character in lemma if is_kanji(character)]
    if kanji_characters:
        return all(character in sentence_ja_text for character in kanji_characters)
    return False
