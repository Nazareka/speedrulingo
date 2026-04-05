# Speedrulingo Backend

This folder contains the FastAPI backend, database layer, domain logic, and the LLM-driven course builder.

## Main Areas

- `src/api/` HTTP routes and request/response schemas
- `src/domain/` application logic for auth, content, learning, and explanations
- `src/db/` SQLAlchemy engine, base models, and persistence setup
- `src/course_builder/` config-driven course generation pipeline
- `alembic/` database migrations
- `scripts/` utility scripts for building and inspecting generated course data

## Highlights

- FastAPI app factory with lifespan setup
- Postgres + SQLAlchemy
- Strict Ruff + Mypy configuration
- ast-grep lint rules
- Course builder with staged planning, assembly, and release validation
- LangGraph-based LLM workflows for vocabulary and sentence generation

## Local Setup

From the repo root:

```bash
docker compose up --build
```

Or run backend-only tooling manually from this directory:

```bash
make lint
make type
make migrate
```

From the repo root, run backend tests against Postgres:

```bash
./run_backend_tests_postgres.sh
```

## Environment

Use [backend/.env.example](/Users/nazareka/projects/Speedrulingo/backend/.env.example) as the starting point for local environment variables.

The backend expects Postgres. Test runs in this repo are intended to run on Postgres only.

## Database Migrations

Schema changes now go through Alembic.

- migration config: [backend/alembic.ini](/Users/nazareka/projects/Speedrulingo/backend/alembic.ini)
- migration environment: [backend/alembic/env.py](/Users/nazareka/projects/Speedrulingo/backend/alembic/env.py)
- revisions: [backend/alembic/versions](/Users/nazareka/projects/Speedrulingo/backend/alembic/versions)

From `backend/`:

```bash
make migrate
```

Or directly:

```bash
env -u VIRTUAL_ENV uv run alembic upgrade head
```

For a new revision:

```bash
env -u VIRTUAL_ENV uv run alembic revision --autogenerate -m "describe change"
```

The app no longer creates tables on startup. A database is expected to already be at the latest migration.

## Course Builder Config Structure

The course builder is config-driven. The main config bundle in this repo is:

- [backend/config/en-ja-v1](/Users/nazareka/projects/Speedrulingo/backend/config/en-ja-v1)

At a high level:

- [course.yaml](/Users/nazareka/projects/Speedrulingo/backend/config/en-ja-v1/course.yaml)
  - global course metadata
  - section order
  - lesson and item settings
  - generation settings
  - runtime distractor settings
  - LLM model settings
- section directories such as [PRE_A1](/Users/nazareka/projects/Speedrulingo/backend/config/en-ja-v1/PRE_A1)
  - `section.yaml`: section metadata and section-planning settings
  - `themes.yaml`: primary and secondary themes
  - `patterns.yaml`: grammar patterns, templates, support forms, anchor rules, and extra-word generation bounds
  - `pattern_examples.yaml`: pattern example sentences and lexicon references used in those examples
  - `bootstrap_words.yaml`: optional early bootstrap/support vocabulary

The config loader also accumulates patterns from previous sections, so later sections are built with awareness of what has already been introduced earlier in the course.

## Course Builder Pipeline

The course builder runs as a staged pipeline. In broad terms, it does this:

1. Import configuration for the target section.
2. Generate section vocabulary with LLM workflows.
3. Generate unit metadata and section curriculum planning.
4. Plan normal lessons and unit structure.
5. Assemble lesson content and lesson items.
6. Run release and acceptance checks for the generated section.

The important point is that this is not one large “generate everything in one prompt” step. The pipeline persists intermediate data and validates each stage before moving to the next one.

## Running Content Generation

The main script for staged content generation is:

- [backend/scripts/run_course_build_step.py](/Users/nazareka/projects/Speedrulingo/backend/scripts/run_course_build_step.py)

From the `backend/` directory, run it like this:

```bash
PYTHONPATH=src uv run python scripts/run_course_build_step.py --config config/en-ja-v1 --build-version 1 --section-code PRE_A1 --all-stages
```

Important flags:

- `--config`
  - path to the course config directory, for example `config/en-ja-v1`
- `--build-version`
  - logical run number for a build attempt
- `--section-code`
  - target section, for example `PRE_A1`
- `--all-stages`
  - run all remaining stages for the section
- `--all-sections`
  - run declared sections in order instead of a single section

The script writes section-specific checkpoints into `backend/build_checkpoints/`, so interrupted runs can resume from the next incomplete stage.

## Notes

- This backend is functional, but it is still a work-in-progress product backend, not a polished production release.
- The most unusual part of the codebase is the course builder, which generates structured course content from configuration and LLM outputs.
