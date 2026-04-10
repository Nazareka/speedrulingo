# ElevenLabs Sentence Audio Plan

## Goal

Add durable sentence audio generation and playback to the existing DBOS-backed course-builder flow.

Requirements from this plan:

1. Generated sentence audio is saved locally on disk.
2. A new workflow generates audio for every sentence in one `build x section`.
3. If the same sentence audio was already generated before, reuse it instead of regenerating it.
4. The workflow only runs for a completed section run.
5. Frontend lesson UI shows a play button when audio exists for the current sentence.

## High-Level Design

Keep the current separation of concerns:

- Postgres remains the source of truth for metadata and workflow/run state.
- DBOS remains the durable workflow engine.
- Local disk stores the actual audio files.
- Frontend consumes backend-provided audio metadata/URLs only.

That implies two layers:

1. `sentence audio metadata` in Postgres
2. `audio binary files` on local disk

Do not treat the filesystem as the source of truth by itself. The DB should say which sentence has which audio asset, where it lives, and whether it is reusable.

## Recommended Scope

Phase this as two implementation slices:

1. Backend generation + persistence + serving
2. Frontend playback button

Do not try to build a full operator UI for audio generation in the first pass unless needed immediately. The core workflow and API matter first.

## Data Model

Add a new table for sentence audio assets.

Suggested table: `sentence_audio_assets`

Suggested fields:

- `id uuid pk`
- `sentence_id uuid not null fk sentences(id) on delete cascade`
- `provider text not null`
- `voice_id text not null`
- `model_id text not null`
- `language_code text not null`
- `text_hash text not null`
- `source_text text not null`
- `storage_path text not null`
- `mime_type text not null`
- `byte_size int not null`
- `status text not null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- `generation_error text null`

Recommended uniqueness:

- `unique (sentence_id, provider, voice_id, model_id, text_hash)`

Why:

- `sentence_id` alone is not enough if you later change voice/model.
- `text_hash` protects reuse when sentence text changes.
- voice/model are part of the identity of the generated asset.

Recommended statuses:

- `pending`
- `ready`
- `failed`

For the first version, there should normally be one `ready` row per reusable variant.

## Local File Storage

Store generated files under a deterministic local root, for example:

`backend/data/sentence_audio/<provider>/<voice_id>/<text_hash>.mp3`

or, if you want course-build traceability in the path while still enabling reuse:

`backend/data/sentence_audio/<provider>/<voice_id>/<sentence_id>/<text_hash>.mp3`

Recommendation:

- use `text_hash` in the filename
- do not key the actual file path by build run
- keep reuse global across builds when the sentence text and voice settings are identical

This matches the requirement that previously generated sentence audio should be reused.

Add a settings entry for the storage root, for example:

- `sentence_audio_storage_root`

and default it to a repo-local directory in dev/docker.

## Reuse Strategy

Reuse should be based on a stable synthesis identity, not just `sentence_id`.

Recommended reuse key:

- `sentence_id`
- normalized Japanese source text
- `provider`
- `voice_id`
- `model_id`

Implementation detail:

1. Load the sentence row and determine the exact text that should be voiced.
2. Normalize that text consistently.
3. Compute `text_hash = sha256(normalized_text + provider + voice_id + model_id)`.
4. Look for an existing `ready` asset row with the same identity.
5. Also verify that the referenced file still exists on disk.
6. Reuse it if present; otherwise generate a new asset.

This avoids accidental regeneration and also protects against stale DB rows pointing at deleted files.

## What Text To Voice

Use the canonical Japanese text stored in `Sentence.ja_text`.

Decision:

- the workflow voices `Sentence.ja_text`
- it does not voice a kana-only display variant

Reasoning:

- `Sentence.ja_text` is the canonical persisted sentence form
- it is the clearest text input for the ElevenLabs model
- kana-only and canonical Japanese should be equivalent in pronunciation for our purposes, so there is no meaningful speech loss from using the canonical form

Implementation note:

- the audio reuse hash should be based on canonical `Sentence.ja_text`, plus provider/voice/model inputs

## New Workflow

Add a separate DBOS workflow dedicated to sentence audio generation, not folded into the main section build workflow.

Suggested workflow:

- `generate_section_sentence_audio_workflow(config: str, build_version: int, section_code: str) -> ...`

Why separate:

- audio generation is operationally distinct from pedagogical content generation
- it may be rerun independently
- it has external-provider latency/cost characteristics
- it should remain resumable on its own

## Gating Rule: Completed Section Run Only

The workflow should only run if the target section build is already complete.

Use runtime queries to resolve the latest relevant section build run for:

- `build_version`
- `config_path`
- `section_code`

Then validate:

- the section run exists
- the section run is `completed`
- the corresponding section content exists in the built `course_version_id`

If not completed, fail fast with a clear domain error such as:

- `Section audio generation requires a completed section build run`

Do not silently trigger content-building steps from the audio workflow.

## Sentence Selection For The Workflow

The workflow should generate audio for all sentences that belong to the built section.

That likely means:

1. resolve the completed section run
2. resolve its `course_version_id`
3. load the section row for `section_code`
4. collect sentences reachable through that section’s units/lessons/items

Prefer deduplicated `sentence_id`s.

Recommended query scope:

- all sentences used in lessons for units in the target section

That matches what learners can encounter in the section.

## Workflow Shape

Recommended DBOS shape:

1. workflow validates completed section build
2. workflow creates a new top-level build run with a distinct scope, for example:
   - `scope_kind = "section_audio"`
3. workflow loads sentence ids for the section
4. workflow iterates sentence ids
5. each sentence generation call is a DBOS step
6. step performs:
   - reuse lookup
   - ElevenLabs call if needed
   - local file write
   - asset metadata upsert

Suggested workflow summary:

- total sentence count
- reused count
- generated count
- failed count

## Runtime/UI Run Tracking

Because the repo already has a clean run model, reuse it instead of creating a second bespoke status system.

Recommended:

- `CourseBuildRun.scope_kind = "section_audio"`
- optional stage runs for coarse phases like:
  - `load_sentences`
  - `generate_sentence_audio`
  - `finalize`

However, sentence-level progress probably matters more than stage-level progress here.

So also add run progress fields through logs and counters:

- `completed_stage_count` is not a great fit for sentence-by-sentence audio generation

Recommendation:

- for phase 1, keep the run model but use log events for per-sentence progress
- if this becomes a serious operator workflow, add explicit `audio_generation_runs` / `audio_generation_items` later

## ElevenLabs Integration

Add a dedicated ElevenLabs integration package under the course-builder source tree:

- `backend/src/course_builder/elevenlabs/client.py`

The wrapper should own:

- auth via API key from settings
- voice/model configuration
- request timeout/retries
- response validation
- content-type handling

Use the official ElevenLabs Python SDK, not handwritten raw HTTP calls.

Settings to add:

- `elevenlabs_api_key`
- `elevenlabs_voice_id`
- `elevenlabs_model_id`
- optional `elevenlabs_base_url`

Do not scatter direct ElevenLabs SDK calls through workflow code.

## File Write Semantics

Write files defensively:

1. generate into a temp path
2. fsync if needed
3. atomically rename to final path
4. upsert DB row only after file is safely in place

That avoids DB rows pointing at partially written files.

## API Changes

The lesson frontend needs to know whether the current sentence has audio and where to fetch it.

The current lesson response already includes:

- `sentence_id`
- sentence token/text data

Extend `LessonItemResponse` in:

- `backend/src/api/learning/schemas.py`

with something like:

- `sentence_audio_url: str | None`

Optionally also:

- `sentence_audio_available: bool`

But `sentence_audio_url | null` is probably enough for the first pass.

Backend service changes:

- in `backend/src/domain/learning/service.py`
- when building a lesson item, if `sentence_id` is present, resolve the best `ready` audio asset and set `sentence_audio_url`

## Audio Delivery

Expose a backend route that serves audio files by asset id or sentence id.

Recommendation:

- serve by asset id, not raw filesystem path

Example route:

- `GET /api/v1/sentence-audio/{asset_id}`

This route:

- loads the metadata row
- verifies the file exists
- returns `FileResponse`

Why not expose raw disk paths:

- avoids coupling frontend to storage layout
- easier to change storage later
- easier to add auth/validation if needed

## Frontend Changes

In the lesson frontend:

- `frontend/src/pages/lesson/index.tsx`

show a play button when:

- current item has `sentence_id`
- and `sentence_audio_url` is not null

Suggested behavior:

- a small audio button near the prompt/header
- click plays audio via a native `HTMLAudioElement`
- disable or show loading state while playback starts

Keep it simple first:

- one button
- replay allowed
- no waveform
- no autoplay

## Frontend API Client Regeneration

Because the backend schema changes, the frontend generated client must be regenerated:

- `cd frontend && npm run generate:api`

And frontend should consume only generated types/hooks/client output.

No handwritten fetch wrapper for sentence audio metadata.

## Operator/UI Flow

Use the existing Reflex operator console as the only launch surface.

Decision:

- do not add a CLI entrypoint for the sentence-audio workflow
- launch and observe it from the Reflex UI only

Suggested operator flow:

- when a completed section build run is selected
- show `Generate sentence audio` button
- launch `section_audio` workflow from Reflex
- show run/log progress in the same console

This fits the current direction of the repo, where orchestration should move toward the Reflex operator surface rather than separate CLI launch commands.

## Error Handling

Expected failures:

- ElevenLabs auth failure
- rate limit / transient provider outage
- invalid voice/model config
- filesystem write failure
- missing completed section build

Recommended behavior:

- fail individual sentence generation steps with clear log events
- persist `failed` status on asset row if a row was created
- keep the workflow resumable and idempotent

## Idempotency Rules

The workflow must be safe to rerun.

For each sentence:

- if reusable ready asset exists and file exists: reuse
- if failed row exists: allow retry
- if partial temp file exists: ignore/replace safely

This keeps DBOS retries safe and prevents duplicate paid synthesis calls.

## Recommended Implementation Order

1. Add settings for ElevenLabs and local storage root.
2. Add `sentence_audio_assets` table + migration.
3. Add query helpers for:
   - latest completed section build run
   - section sentence ids
   - audio asset lookup
4. Add ElevenLabs client wrapper.
5. Add file storage service for local save/load.
6. Add DBOS workflow + step for section sentence audio generation.
7. Add backend route to serve audio by asset id.
8. Extend lesson API schema with `sentence_audio_url`.
9. Regenerate frontend API client.
10. Add lesson play button.
11. Optionally add operator-console trigger for audio workflow.

## Concrete Backend Modules To Add

Suggested new files:

- `backend/src/course_builder/elevenlabs/client.py`
- `backend/src/course_builder/elevenlabs/__init__.py`
- `backend/src/domain/content/audio_models.py` or keep in `domain/content/models.py`
- `backend/src/domain/content/audio_queries.py`
- `backend/src/domain/content/audio_service.py`
- `backend/src/course_builder/runtime/audio_workflows.py` or integrate into existing `runtime/dbos.py`

If you keep the current runtime organization, the most consistent place is:

- DBOS workflow entrypoints in `backend/src/course_builder/runtime/dbos.py`
- orchestration/query helpers in the existing runtime/domain layers

## Recommendation On Where To Keep Sentence Audio Models

Prefer keeping `SentenceAudioAsset` in:

- `backend/src/domain/content/models.py`

Reason:

- audio is part of persisted built content delivery, not purely runtime orchestration state

The workflow/run records stay in runtime tables; the produced audio asset metadata belongs with content tables.

## Open Decisions To Review

These should be resolved before implementation:

1. Which exact Japanese text variant should be voiced?
2. Which ElevenLabs voice/model should be the initial default?
3. Should reuse be global across all builds, or only within the same `course_version` family?
4. Do we want only lesson-surfaced sentences, or every sentence linked to the section?

## My Recommended Answers

1. Voice canonical `Sentence.ja_text`.
2. Start with one configured voice/model in settings.
3. Reuse globally when `sentence text + voice/model` are identical.
4. Generate for all lesson-reachable section sentences.

## Minimal First-Version Success Criteria

The first version is successful if:

- you can launch `generate_section_sentence_audio_workflow(config, build_version, section_code)`
- it refuses to run for incomplete sections
- it saves audio files locally
- reruns reuse existing assets without new synthesis
- lesson API exposes `sentence_audio_url`
- lesson frontend shows a play button when audio exists
