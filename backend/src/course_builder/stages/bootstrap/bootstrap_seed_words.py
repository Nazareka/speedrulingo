from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.queries.bootstrap import BootstrapQueries
from domain.content.models import SectionWord, Word


@dataclass(frozen=True, slots=True)
class BootstrapWordInsertStats:
    words_created: int
    section_words_created: int


def insert_bootstrap_seed_words(db: Session, *, context: BuildContext) -> BootstrapWordInsertStats:
    q = BootstrapQueries(db, context.course_version_id, context.section_code)
    section_id = q.get_section_id()
    if section_id is None:
        msg = f"Section config must be imported before bootstrap seed words for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    words: list[Word] = []
    support_words = list(context.config.bootstrap.support_words)
    all_bootstrap_words = [*support_words, *context.config.bootstrap.seed_words]

    for index, seed_word in enumerate(all_bootstrap_words, start=1):
        is_seed_word = seed_word in context.config.bootstrap.seed_words
        word = Word(
            course_version_id=context.course_version_id,
            intro_order=index,
            canonical_writing_ja=seed_word.canonical_writing_ja,
            reading_kana=seed_word.reading_kana,
            gloss_primary_en=seed_word.gloss_primary_en,
            gloss_alternatives_en=seed_word.gloss_alternatives_en,
            usage_note_en=seed_word.usage_note_en,
            pos=seed_word.pos.value,
            source_kind="manual_seed" if is_seed_word else "manual_support",
            generation_pipeline=None,
        )
        words.append(word)
    db.add_all(words)
    db.flush()

    section_words = [
        SectionWord(
            section_id=section_id,
            word_id=word.id,
            role="new",
        )
        for word in words
        if word.source_kind == "manual_seed"
    ]
    db.add_all(section_words)
    db.commit()

    return BootstrapWordInsertStats(
        words_created=len(words),
        section_words_created=len(section_words),
    )


class InsertBootstrapSeedWordsStep(BuildStep):
    name = "insert_bootstrap_seed_words"

    @override
    def run(self, *, db: Session, context: BuildContext) -> BootstrapWordInsertStats:
        if not context.config.bootstrap.support_words and not context.config.bootstrap.seed_words:
            return BootstrapWordInsertStats(words_created=0, section_words_created=0)
        q = BootstrapQueries(db, context.course_version_id, context.section_code)
        if q.exists_words_for_current_section():
            msg = (
                f"Bootstrap seed words already exist for course_version_id={context.course_version_id} "
                f"section_code={context.section_code}"
            )
            raise ValueError(msg)
        return insert_bootstrap_seed_words(db, context=context)
