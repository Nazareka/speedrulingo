# Course Builder

This folder contains the config-driven course generation pipeline used to build Speedrulingo course content.

It is not just “prompt the LLM and save the result”. The system is a staged compiler-like pipeline that:

- imports deterministic config and catalog data
- generates and persists vocabulary needed for the current section
- plans unit and lesson structure
- assembles sentences, items, hints, kanji introductions, review lessons, and exams
- runs strict acceptance checks before publishing a course build

## Important Note

This README may become outdated as the course builder changes.

Codex note:
- do not update this README unless the user explicitly asks for it

## What It Produces

At a high level, the course builder produces persisted course data for one section of one course build version:

- patterns
- theme tags
- sections
- words
- sentences
- planned units and planned lessons
- published units and lessons
- lesson items
- kanji introductions and hint payloads

The output is stored in the main backend database and becomes part of the active course after the release stage publishes the build.

## Main Stack

The course builder is mostly Python + SQLAlchemy, with LangGraph-based LLM workflows for specific generation tasks.

Core pieces:

- Python 3.12+
- SQLAlchemy ORM and direct stage/query persistence
- Postgres as the intended database
- Pydantic config models for strict YAML validation
- LangGraph for LLM generation graphs
- LangChain OpenAI/OpenRouter integrations via shared client helpers
- Fugashi / UniDic-based sentence processing utilities for Japanese tokenization and analysis

## Folder Structure

Important subfolders:

- [config.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/config.py)
  - strict config models and loader logic for the course YAML bundle
- [runtime/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/runtime)
  - build context, checkpointing, stage orchestration, and stage registry
- [stages/bootstrap/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/bootstrap)
  - deterministic import of theme tags, pattern catalog, section config, and bootstrap seed words
- [stages/planning/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/planning)
  - vocabulary generation, section curriculum planning, unit metadata generation, and normal lesson planning
- [stages/assembly/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/assembly)
  - sentence persistence, review/exam creation, tile generation, lesson item generation, hints, and kanji introductions
- [stages/release/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/release)
  - section acceptance checks and publication logic
- [queries/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/queries)
  - stage-specific database reads grouped by pipeline phase
- [llm/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm)
  - LangGraph workflows for mechanical words, anchored words, pattern vocabulary, master pattern vocab orchestration, and unit metadata
- [sentence_processing/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/sentence_processing)
  - Japanese sentence normalization, parsing, tokenization, chunking, and hint generation support

## How It Is Used

The main entrypoint is:

- [run_course_build.py](/Users/nazareka/projects/Speedrulingo/backend/scripts/run_course_build.py)

Typical usage from `backend/`:

```bash
PYTHONPATH=src .venv/bin/python3 scripts/run_course_build.py \
  --config config/en-ja-v1 \
  --build-version 1 \
  --section-code PRE_A1 \
  --all-stages
```

Important flags:

- `--config`
  - path to the course config bundle
- `--build-version`
  - logical build attempt number
- `--section-code`
  - the section to build
- `--all-stages`
  - run all remaining stages for that section
- `--all-sections`
  - run declared sections in order instead of one section

Build checkpoints are stored in Postgres, so interrupted runs can resume from the next incomplete stage without filesystem checkpoint files.

The build is now orchestrated through Prefect flows, but the underlying runtime/checkpoint system is still the source of truth for stage execution and resuming.

## Stage Order

The stage order is defined in [stage_registry.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/runtime/stage_registry.py).

Current build stages:

1. `bootstrap_catalog`
2. `pattern_vocab_generation`
3. `section_curriculum_planning`
4. `unit_metadata_generation`
5. `plan_normal_lessons`
6. `content_assembly`
7. `release`

There is also an implicit stage 0 in the runtime layer that creates the draft `course_version` build row before the first real stage runs.

## What Each Stage Does

### 1. Bootstrap

Implemented in [stages/bootstrap/stage.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/bootstrap/stage.py).

This imports deterministic config data for the section:

- theme tags
- pattern catalog
- section config and links
- bootstrap seed/support words

This stage does not rely on the LLM.

### 2. Pattern Vocab Generation

Implemented in [stages/planning/pattern_vocab_generation.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/planning/pattern_vocab_generation.py).

This stage generates missing vocabulary needed for the current section:

- mechanical lexemes derived from pattern examples
- anchored lexical words derived from explicitly referenced example lexemes
- extra lexical words generated for patterns with `min_extra_words` / `max_extra_words`

It persists:

- generated words
- generated word example sentences
- section word links
- word theme links for section-owned lexical generation

The current architecture prepares pattern-specific runs, then executes them through one master LangGraph orchestration graph.

### 3. Section Curriculum Planning

Implemented in [stages/planning/section_curriculum_planning.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/planning/section_curriculum_planning.py) and [stages/planning/section_curriculum.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/planning/section_curriculum.py).

This is the deterministic planning core.

It builds the section teaching flow:

- pattern bundles
- sentence-introduction waves
- normal-lesson waves
- unit chunking
- kanji activation insertion after the configured threshold

It persists `planned_units` and `planned_lessons`, which are the intermediate teaching plan that later stages consume.

Current planning direction:

- sentence-first planning
- normal units shaped around 2–3 normal lessons
- bootstrap special case for the first section
- explicit kanji activation block after kanji display turns on

### 4. Unit Metadata Generation

Implemented in [stages/planning/unit_metadata_generation.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/planning/unit_metadata_generation.py).

This takes the deterministic planned units and generates learner-facing metadata:

- unit titles
- unit descriptions
- unit theme tags

It also persists unit-level ownership metadata:

- `UnitWord`
- `UnitPatternLink`
- `UnitThemeLink`

### 5. Normal Lesson Planning

Implemented in [stages/planning/normal_lesson_planning.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/planning/normal_lesson_planning.py).

This converts the planned lesson waves into real persisted normal lessons and their lesson-level ownership links:

- `Lesson`
- `LessonWord`
- `LessonPatternLink`

This is still pre-assembly: it creates the lesson shells and ownership links, not the final items.

### 6. Content Assembly

Implemented in [stages/assembly/stage.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/assembly/stage.py).

This stage materializes the actual teachable content:

- persists section-owned pattern example sentences
- creates algorithmic review and exam lessons
- builds sentence tile sets
- generates lesson items
- builds hints and kanji introductions

The output of this stage is close to what the learner actually consumes.

### 7. Release

Implemented in [stages/release/stage.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/stages/release/stage.py).

This stage:

- runs strict acceptance checks over the generated section
- publishes the build if checks pass
- archives the previous active course version when needed

This is the final gate that prevents obviously broken generated content from becoming the active course.

## LLM Workflows

The LLM code is isolated under [llm/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm).

Important graphs:

- [mechanical_word_generation/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm/mechanical_word_generation)
  - generates gloss metadata for mechanical lexemes
- [anchored_word_generation/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm/anchored_word_generation)
  - generates lexical metadata and examples for requested lexemes
- [pattern_vocab_generation/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm/pattern_vocab_generation)
  - generates extra lexical words for a pattern
- [master_pattern_vocab_generation/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm/master_pattern_vocab_generation)
  - master LangGraph that runs the pattern vocabulary generation flow pattern-by-pattern
- [unit_metadata_generation/](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/llm/unit_metadata_generation)
  - generates unit titles/descriptions/theme allocation

LLM output is validated aggressively with:

- strict JSON schema shaping
- deterministic structural checks
- domain-specific validation in graph nodes and planning stages

## Config Model

The course builder is fully driven by a config bundle such as:

- [backend/config/en-ja-v1](/Users/nazareka/projects/Speedrulingo/backend/config/en-ja-v1)

At a high level:

- `course.yaml`
  - global course metadata, lesson settings, generation settings, runtime settings, section order, and LLM model names
- per-section directory
  - `section.yaml`
  - `themes.yaml`
  - `patterns.yaml`
  - `pattern_examples.yaml`
  - optional `bootstrap_words.yaml`

The config layer is intentionally strict. The Pydantic models in [config.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/config.py) reject malformed or contradictory config early.

## Runtime Model

The runtime layer gives the course builder a resumable, stage-based build process:

- [runtime/models.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/runtime/models.py)
  - build context and stage protocol
- [runtime/runner.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/runtime/runner.py)
  - checkpoint-aware execution of one stage at a time
- [runtime/persistence.py](/Users/nazareka/projects/Speedrulingo/backend/src/course_builder/runtime/persistence.py)
  - draft build row creation

This lets the pipeline:

- build one section at a time
- run one stage at a time
- resume after failures
- enforce section order dependencies

## Notes on Current Reality

This folder contains real project code, not a tutorialized example.

That means a few important things:

- some internal planning rules were revised multiple times and the code reflects those iterations
- acceptance checks are intentionally strict because the generation pipeline still needs hard guards
- unit metadata generation currently includes stubbed behavior while prompt-size and strategy are still being reworked
- there are helper docs and historical design notes elsewhere in the repo, but the Python code in this folder is the source of truth
