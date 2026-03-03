from langchain_core.prompts import ChatPromptTemplate

from course_builder.llm.core.prompts import build_chat_prompt

SYSTEM_PROMPT = """You generate lexical metadata for mechanical Japanese lexemes.

Rules:
- Return one item for each requested lexeme.
- gloss_primary_en must be short and clean.
- Do not use slashes or semicolons in gloss_primary_en.
- Keep the requested lemma, reading, and part of speech unchanged.
- Generate only gloss metadata.
- Put only genuinely useful alternates into gloss_alternatives_en.
- Put nuance or usage restrictions into usage_note_en.
"""

HUMAN_PROMPT = """<mechanical_word_generation_request>
<requested_lexemes>{requested_lexemes}</requested_lexemes>
</mechanical_word_generation_request>"""
MECHANICAL_WORD_GENERATION_PROMPT: ChatPromptTemplate = build_chat_prompt(
    system_prompt=SYSTEM_PROMPT,
    human_prompt=HUMAN_PROMPT,
)
