# ElevenLabs Word Audio Plan

## Goal

Add durable word-audio generation to the existing DBOS-backed course-builder flow.

Requirements from this plan:

1. Generated word audio is saved locally on disk.
2. A new workflow generates audio for every relevant word in one `build x section`.
3. If the same word audio was already generated before, reuse it instead of regenerating it.
4. The workflow only runs for a completed section run.
5. Word audio and sentence audio remain separate workflows and separate asset types.
6. The ElevenLabs input text for words is always `Word.canonical_writing_ja`.

## High-Level Design

Keep the same architecture already used for sentence audio:

- Postgres remains the source of truth for metadata and workflow/run state.
- DBOS remains the durable workflow engine.
- Local disk stores the actual audio files.
- Consumers use backend-provided metadata/URLs only.

That implies two layers:

1. `word audio metadata` in Postgres
2. `audio binary files` on local disk

Word audio should not be folded into sentence audio. These are different entity types with different source text, reuse identity, and future playback surfaces.

## Separation From Sentence Audio

There should be two separate workflows:

1. `generate_section_sentence_audio_workflow(...)`
2. `generate_section_word_audio_workflow(...)`

There should also be separate persistence models and admin controls:

- `sentence_audio_assets`
- `word_audio_assets`

Do not use one generic polymorphic table unless there is a very strong reason later. The current codebase is clearer with one table per content type.

## Data Model

Add a new table for word audio assets.

Suggested table: `word_audio_assets`

Suggested fields:

- `id uuid pk`
- `word_id uuid not null fk words(id) on delete cascade`
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

- `unique (word_id, provider, voice_id, model_id, text_hash)`

Why:

- `word_id` alone is not enough if the voice or model changes later.
- `text_hash` protects reuse when the canonical writing changes.
- provider, voice, and model are part of the generated asset identity.

Recommended statuses:

- `pending`
- `ready`
- `failed`

## What Text To Voice

Use `Word.canonical_writing_ja` as the source text sent to ElevenLabs.

Decision:

- word audio always voices `Word.canonical_writing_ja`
- word audio does not voice `reading_kana`

Reasoning:

- `canonical_writing_ja` is the canonical persisted lexeme form in the domain model
- this matches the requested product behavior
- the workflow should not choose display variants dynamically

Implementation note:

- the reuse hash must be based on normalized `Word.canonical_writing_ja`, plus provider/voice/model inputs

## Local File Storage

Store generated files under a deterministic local root, for example:

`backend/data/word_audio/<provider>/<voice_id>/<text_hash>.mp3`

Recommendation:

- use `text_hash` in the filename
- do not key the path by build run
- keep reuse global across builds when canonical writing and voice settings are identical

This mirrors the sentence-audio strategy and avoids unnecessary regeneration.

## Reuse Strategy

Reuse should be based on a stable synthesis identity, not just `word_id`.

Recommended reuse key:

- `word_id`
- normalized Japanese source text from `Word.canonical_writing_ja`
- `provider`
- `voice_id`
- `model_id`

Implementation detail:

1. Load the word row and determine the exact text to voice.
2. Normalize that text consistently.
3. Compute `text_hash = sha256(normalized_text + provider + voice_id + model_id)`.
4. Look for an existing `ready` asset row with the same identity.
5. Verify that the referenced file still exists on disk.
6. Reuse it if present; otherwise generate a new asset.

## Section Selection For The Workflow

The workflow should generate audio for all relevant words in the built section.

Recommended first-pass scope:

- deduplicated `word_id`s belonging to the target section
- ordered by `Word.intro_order`, then `Word.canonical_writing_ja`

Recommended interpretation of “relevant words”:

- all words persisted for the section’s course build that can surface in the section’s lessons

If that proves too broad operationally, narrow it to:

- words introduced in units of the target section

But decide this explicitly in the query helper rather than leaving it implicit.

Suggested query helper:

- `list_section_word_ids(db, course_version_id, section_code) -> list[str]`

## New Workflow

Add a separate DBOS workflow dedicated to word audio generation.

Suggested workflow:

- `generate_section_word_audio_workflow(config: str, build_version: int, section_code: str) -> ...`

Why separate:

- word audio is operationally distinct from sentence audio
- it may be rerun independently
- it has separate progress, cost, and failure characteristics
- it should remain resumable on its own

## Gating Rule: Completed Section Run Only

The workflow should only run if the target section build is already complete.

Use the same runtime query pattern as sentence audio:

- resolve the latest completed section build run for `build_version`, `config_path`, and `section_code`
- validate the run exists and has a `course_version_id`

If not completed, fail fast with a clear error such as:

- `Section word audio generation requires a completed section build run`

Do not silently trigger content-building steps from the word-audio workflow.

## Workflow Shape

Recommended DBOS shape:

1. workflow validates completed section build
2. workflow creates a new top-level build run with:
   - `scope_kind = "section_word_audio"`
3. workflow loads section `word_id`s
4. workflow iterates words
5. each word generation call is a DBOS step
6. step performs:
   - reuse lookup
   - ElevenLabs call if needed
   - local file write
   - asset metadata upsert

Suggested workflow summary:

- total word count
- reused count
- generated count
- failed count

Suggested summary type:

- `SectionWordAudioSummary`

Suggested fields:

- `build_run_id`
- `source_section_build_run_id`
- `build_version`
- `section_code`
- `total_word_count`
- `generated_word_count`
- `reused_word_count`
- `failed_word_count`

## Service Layer

Add word-audio helpers parallel to the existing sentence-audio helpers.

Suggested functions:

- `word_audio_identity(...)`
- `get_word_audio_asset(...)`
- `get_ready_word_audio_asset(...)`
- `get_word_audio_asset_by_identity(...)`
- `create_or_update_word_audio_asset(...)`
- `ensure_word_audio_asset(word_id=...)`
- `mark_word_audio_asset_failed(word_id=..., error_message=...)`
- `build_word_audio_url(asset_id=...)`
- `resolve_word_audio_url(word_id=...)`

Keep the service-level rule explicit:

- sentence audio uses `Sentence.ja_text`
- word audio uses `Word.canonical_writing_ja`

## ElevenLabs Integration

Reuse the existing wrapper in:

- `backend/src/course_builder/elevenlabs/client.py`

Do not add a second client just for words.

The service layer decides what text to send:

- sentence flow sends sentence text
- word flow sends canonical word writing

## Runtime/UI Run Tracking

Reuse the existing `CourseBuildRun` model the same way sentence audio does.

Recommended:

- `scope_kind = "section_word_audio"`
- per-word progress tracked through logs plus `completed_stage_count`

Suggested log lines:

- `Starting section word audio generation ...`
- `Reused word audio word_id=... voice_id=...`
- `Generated word audio word_id=... voice_id=...`
- `Word audio generation failed word_id=... error=...`

## Admin And Operator Controls

Add a separate operator trigger for word audio:

- `Generate word audio`

Do not overload the sentence-audio button or workflow.

Add a separate admin page:

- `/admin/word-audio`

Recommended admin capabilities:

- show asset count
- show latest asset
- wipe all word audio from DB and disk

Keep sentence and word wipe actions separate.

## Optional Delivery API

Even if frontend playback is deferred, the backend should have a clean serving path ready.

Suggested route:

- `GET /api/v1/word-audio/{asset_id}`

Security should mirror sentence audio:

- only serve assets accessible within the requesting user’s active course context

If playback is added later, the UI should consume backend-provided `word_audio_url`, not construct URLs manually.

## Recommended Implementation Order

1. Add `word_audio_assets` migration and ORM model.
2. Add word-audio service helpers and reuse logic.
3. Add section-word selection query.
4. Add DBOS step + workflow.
5. Add workflow summary/export wiring.
6. Add operator UI trigger.
7. Add admin page + wipe action.
8. Optionally add serving route and frontend playback.

## Key Decisions

- Use `Word.canonical_writing_ja` as the ElevenLabs input text.
- Keep word audio fully separate from sentence audio at the workflow, table, route, and admin levels.
- Mirror the sentence-audio architecture rather than inventing a second audio subsystem shape.

## Main Risks

- Section word selection can drift if the query scope is not explicit.
- Reuse identity must hash canonical writing plus provider/voice/model, not just `word_id`.
- If canonical writing normalization is inconsistent, reuse may fragment and cause unnecessary regeneration.

## Definition Of Done

This feature is done when:

1. `generate_section_word_audio_workflow(config, build_version, section_code)` can be launched independently
2. it only runs when the section build is already completed
3. it voices `Word.canonical_writing_ja`
4. it saves files locally
5. it reuses existing matching assets when possible
6. it tracks run progress through the existing runtime model
7. it has separate admin/operator controls from sentence audio
