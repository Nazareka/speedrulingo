from langchain_core.prompts import ChatPromptTemplate

from course_builder.llm.core.prompts import build_chat_prompt

SYSTEM_PROMPT = """You generate learner-facing metadata for already planned units in a Japanese course compiler.

Rules:
- Return metadata for every unit in order.
- Use only provided theme codes.
- Words and patterns are already allocated by code. Do not redesign the allocation in your head; use the provided unit allocation as the pedagogical content for each unit.
- Your job is only to provide strong unit metadata:
  - a concise title
  - a concise learner-facing description
  - 1 or more matching theme codes
- Respect the already planned unit contents.
- Return valid structured data only.
"""

HUMAN_PROMPT = """<unit_plan_request>
<section_title>{section_title}</section_title>
<section_description>{section_description}</section_description>
<section_theme_codes>{section_theme_codes}</section_theme_codes>
<unit_specs>{unit_specs}</unit_specs>
<allocated_unit_content>{allocated_unit_content}</allocated_unit_content>
</unit_plan_request>"""
UNIT_METADATA_GENERATION_PROMPT: ChatPromptTemplate = build_chat_prompt(
    system_prompt=SYSTEM_PROMPT,
    human_prompt=HUMAN_PROMPT,
)
