from langchain_core.prompts import ChatPromptTemplate

from course_builder.llm.core.prompts import build_chat_prompt

SYSTEM_PROMPT = """You generate extra Japanese vocabulary for a course compiler.

Rules:
- Return only extra words appropriate for the current scope.
- DO NOT REPEAT ANY LEMMA ALREADY PRESENT IN existing_words.
- Use only allowed part-of-speech labels.
- Prefer practical, neutral, everyday beginner-safe vocabulary.
- Prefer words that work well with the provided pattern scope.
- Avoid words that are awkward or hard to use with the provided pattern scope.
- Avoid near-duplicates of existing lemmas unless the new word adds clear beginner value.

Lexical quality rules:
- Generate only atomic, dictionary-form lemmas with clear standalone beginner value.
- Treat as duplicates not only exact lemma matches, but also script/orthography variants, kana/kanji variants, and trivial spelling variants of existing_words.
- Do not generate items whose meaning is transparently compositional from already known words or patterns, including fixed chunks, inflected forms, copula-attached forms, particle-attached forms, and simple modifier+noun phrases.
- Do not generate words that are primarily better taught as a pattern slot or a predictable phrase rather than as an independent vocabulary item.
- Do not generate overly narrow, context-dependent, honorific, or omission-prone items unless they provide strong standalone beginner value.
- Prefer base forms over derived, marked, or phrase-level variants.

Translation rules:
- gloss_primary_en must be short and clean.
- Do not use slashes or semicolons in gloss_primary_en.
- Put only genuinely useful alternate meanings into gloss_alternatives_en.
- Put nuance or restricted usage into usage_note_en, not into gloss_primary_en.

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

HUMAN_PROMPT = """<extra_word_generation_request>
<scope_title>{scope_title}</scope_title>
<scope_description>{scope_description}</scope_description>
<primary_themes>{primary_themes}</primary_themes>
<secondary_themes>{secondary_themes}</secondary_themes>
<patterns_scope>{patterns_scope}</patterns_scope>
<existing_words>{existing_words}</existing_words>
</extra_word_generation_request>"""
PATTERN_VOCAB_GENERATION_PROMPT: ChatPromptTemplate = build_chat_prompt(
    system_prompt=SYSTEM_PROMPT,
    human_prompt=HUMAN_PROMPT,
)
