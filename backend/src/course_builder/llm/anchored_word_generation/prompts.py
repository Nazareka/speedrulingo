from langchain_core.prompts import ChatPromptTemplate

from course_builder.llm.core.prompts import build_chat_prompt

SYSTEM_PROMPT = """You generate lexical metadata and example sentences for explicitly requested Japanese words.

Rules:
- Return one item for each requested target.
- gloss_primary_en must be short and clean.
- Do not use slashes or semicolons in gloss_primary_en.
- Keep each requested lemma, reading, and part of speech unchanged.
- Generate clean lexical metadata plus exactly 2 example sentences.

Example sentence rules:
- Return exactly 2 example_sentences for each generated word.
- it must include the generated word.
- Each example sentence must contain:
  - ja_text
  - en_text
- Example sentences should be natural, useful, beginner-safe, and should use the generated word in its canonical writing. for example, use 私 not わたし
- Example sentences must be ordinary Japanese utterances, not explanations about the target word itself.
- Example sentence must use patterns from patterns_scope.
- Use words only from existing_words.
- Treat existing_words as a closed lexicon for example sentences.
- Do not introduce any extra lemma that is not explicitly present in existing_words, including support verbs, light verbs, helper nouns, particles, or default collocations. The only exception is inflecting the target word itself when required by an allowed pattern.
- Avoid unnatural, low-value, context-dependent, or overly dense combinations.
- Avoid placeholder-like sentences.
- Avoid category mistakes such as people being food or objects.
- Avoid awkward beginner-Japanese errors such as malformed demonstrative usage, malformed question usage, or malformed possession usage.
- Avoid overly literal English translations.
- Prefer complete standalone sentences over dialogue responses, elliptical answers, label-like fragments, or bare noun phrases.
- Do not produce label-like, dictionary-like, or identification-fragment sentences that depend on omitted context.
- Avoid outputs that feel like short answers to an unseen question rather than natural beginner sentences.
- Avoid sentences that are grammatically possible but pragmatically odd, overly specific, or low-value for a learner.
- Do not use contrastive or additive particles unless the sentence still sounds natural as a standalone beginner utterance.
- Translate the actual sentence naturally and simply.
- Do not preserve Japanese awkwardness in English.
- Do not include alternate glosses in the translation.
- Do not insert spaces between Japanese words or particles.
- Use only one clean English translation.
- Do not use slashes, semicolons, or parentheses in the English translation.
- Do not use『 』「」.

"""

HUMAN_PROMPT = """<anchored_word_generation_request>
<patterns_scope>{patterns_scope}</patterns_scope>
<current_words>{current_words}</current_words>
<targets>{targets}</targets>
</anchored_word_generation_request>"""
ANCHORED_WORD_GENERATION_PROMPT: ChatPromptTemplate = build_chat_prompt(
    system_prompt=SYSTEM_PROMPT,
    human_prompt=HUMAN_PROMPT,
)
