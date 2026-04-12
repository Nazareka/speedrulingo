# Kana Learning Feature Plan

## Goal

Add a dedicated hiragana/katakana learning flow with:

1. A kana overview page that shows every character, its script, and per-character learning progress.
2. A kana lesson experience that reuses the current lesson shell where possible, but serves kana-specific item types.
3. A separate audio-generation workflow for kana audio, with reuse across kana and word audio when the spoken text is identical.

## Decided Product Direction

Based on your answers, v1 should follow these rules:

- one combined kana learning queue across hiragana and katakana
- exposure target is `6` per character
- queue strategy is hiragana-first, then gradual katakana mix
- voiced kana should be introduced base-first
- small kana are in scope; the catalog should be complete
- kana learning is fully independent from the main course path
- character mastery is exposure-based, not correctness-count-based
- `Continue learning` should always create a fresh next lesson, not resume unfinished kana lessons
- lessons may mix hiragana and katakana
- audio should be reused across hiragana and katakana when pronunciation is the same
- broader audio refactor is acceptable if it makes the code cleaner

## Product Shape

### User-facing behavior

- Add a new page for kana study:
  - one section for hiragana
  - one section for katakana
  - each character tile shows progress, locked/available/mastered state
  - one primary CTA: `Continue learning`
- Add kana lessons with two item formats:
  - `audio_to_kana_choice`: play one audio, choose 1 of 4 kana characters
  - `kana_to_audio_choice`: show one kana character, choose 1 of 4 audio options
- No romaji anywhere in the learner-facing flow.
- Kana should be introduced from easier to harder groups, but lesson composition should still vary so consecutive lessons are not repetitive.

### Learning behavior

- Each kana character must be seen multiple times before it is considered learned.
- Progress should be tracked per character, not only per lesson.
- Lesson construction should be guided, not random:
  - prioritize not-yet-mastered characters
  - strongly prefer characters from the current difficulty band
  - keep a smaller amount of review from already-seen characters
  - vary prompts/distractors/order so lessons stay fresh

## Recommended Domain Model

### New core concepts

Add a dedicated kana-learning domain instead of trying to force kana into the existing word/sentence lesson model.

Suggested backend entities:

- `kana_character`
  - static catalog row per character
  - fields:
    - `id`
    - `script` (`hiragana|katakana`)
    - `char`
    - `group_key` for teaching groups
    - `difficulty_rank`
    - `is_voiced`
    - `is_small_variant`
    - `base_char` for voiced/small variants if applicable
- `kana_audio_asset`
  - optional dedicated table if we want explicit ownership for kana assets
  - stores provider/model/voice/text hash/path/status similarly to current audio assets
- `user_kana_progress`
  - one row per user per character
  - fields:
    - `times_seen`
    - `times_prompted_as_character`
    - `times_prompted_as_audio`
    - `mastery_score`
    - `state` (`new|learning|review|mastered`)
    - timestamps for scheduling
- `kana_lesson`
  - lesson session container for kana mode
- `kana_lesson_item`
  - item rows for kana lesson content
  - item type:
    - `audio_to_kana_choice`
    - `kana_to_audio_choice`

### Why separate from current content lessons

Separate modeling is cleaner because:

- current `LessonItemResponse` is built around text prompts and text answer tiles
- kana progression is per character, not per course lesson
- kana lesson completion should not distort the main course path progression
- we need new item payloads that include multiple audio options, which current API does not model well

## Audio Strategy

### Recommendation

Build a separate kana audio generation workflow, but reuse the same normalization and dedup rules as word audio.

### Why

- kana has its own inventory and should be backfillable independently of course builds
- audio generation may happen before any course version exists
- the same spoken text should reuse the same binary asset whether it came from a kana row, a hiragana row, a katakana row, or a word row

### Recommended implementation

1. Extract a shared audio identity layer from `backend/src/domain/content/audio_service.py`.
2. Normalize by spoken Japanese text only, plus provider/voice/model.
3. Introduce a reusable shared-audio lookup abstraction.
4. Let word audio and kana audio both point to the same underlying file when `source_text` matches exactly.
5. Do not generate separate assets for hiragana vs katakana if pronunciation is the same.

### Design choice

There are two viable storage designs:

- Preferred:
  - create a shared `audio_asset` table keyed by normalized text hash and provider/voice/model
  - have `word_audio_asset`, `sentence_audio_asset`, and `kana_audio_asset` reference it
- Simpler first step:
  - keep existing tables
  - add kana audio using the same hash computation and allow cross-table reuse at file level

Decision: do the broader shared-audio refactor now if it keeps the ownership boundaries clean.

## Lesson Planning Strategy

### Teaching order

Define an explicit kana syllabus instead of deriving order on the fly.

Suggested grouping:

1. Basic vowels and easiest high-frequency kana
2. Easy `k/s/t/n/h/m/y/r/w` hiragana rows
3. Start gradual katakana mix for already-familiar sounds
4. Dakuten and handakuten variants mixed in after their base characters were introduced
5. Small kana and extended katakana combinations

Each character should have:

- `difficulty_rank`
- `group_key`
- `target_exposures`

### Lesson construction heuristic

For each generated kana lesson:

1. Select a current focus set from the earliest not-mastered group.
2. Fill most items from that focus set.
3. Add a smaller review slice from recent or weak characters.
4. For each selected character, schedule both recognition directions over time:
   - audio -> kana
   - kana -> audio
5. Avoid repeating the exact same distractor set too often.

Suggested initial policy:

- lesson size: 8 to 12 items
- 60-70% current focus characters
- 30-40% review characters
- exposure target: `6` completed item exposures per character
- each active character appears until `target_exposures` is met
- characters advance to `mastered` after the exposure threshold is met through completed lessons
- unfinished kana lessons do not persist; the next `Continue learning` call should plan a new lesson from current progress state

### Distractor strategy

Distractors should not be random from the full kana set. Prefer visually or phonetically confusing neighbors:

- same row
- same voicing family
- same diacritic family
- visually similar shapes

This makes the lessons more educational and less noisy.

## API Plan

If backend routes or schemas change, regenerate the frontend API client with `npm run generate:api`.

### New backend routes

Add a separate kana API namespace, for example:

- `GET /api/v1/kana/overview`
  - returns all kana grouped by script with progress summary
- `POST /api/v1/kana/continue`
  - creates a fresh next kana lesson from current progress and returns its id
- `GET /api/v1/kana/lessons/{lesson_id}/next-item`
  - returns kana lesson item payload
- `POST /api/v1/kana/lessons/{lesson_id}/submit`
  - submits one or more kana answers and updates per-character progress
- `GET /api/v1/kana/audio/{asset_id}`
  - serves kana audio if we keep a dedicated kana asset route

### New response shapes

Add kana-specific schemas instead of overloading the current lesson schema:

- `KanaOverviewResponse`
- `KanaCharacterProgress`
- `KanaLessonItemResponse`
- `KanaSubmitResponse`

`KanaLessonItemResponse` should support both item shapes directly, including multiple audio-option ids/URLs for `kana_to_audio_choice`.

## Frontend Plan

### New page

Add a dedicated route, for example `frontend/src/pages/kana-page.tsx`.

Responsibilities:

- fetch overview
- render hiragana and katakana grids
- show per-character progress
- call `continue learning`
- route into the active kana lesson

### New lesson UI

Do not force kana learning into the exact current lesson item renderer without a boundary.

Recommended approach:

- keep the lesson page shell patterns
- add kana-specific presentation components:
  - `KanaAudioPromptCard`
  - `KanaAudioChoiceGrid`
  - `KanaCharacterPromptCard`
  - `KanaAudioChoiceList`
- share generic session state patterns where possible
- keep kana lesson item rendering in a separate branch from standard content lessons

### Progress display

For each kana tile show:

- character only
- mastery/progress ring or bar
- optional state styling: `new`, `learning`, `review`, `mastered`

No romaji labels.

## Backend Workflow Plan

### Kana catalog bootstrap

Create a static kana catalog source in backend code or seed data:

- canonical hiragana set
- canonical katakana set
- metadata for group order and difficulty

This should not depend on course build.

### Audio workflow

Add a separate workflow/command for kana audio generation:

- backfill all kana audio assets
- regenerate missing or failed items
- optionally scope by script or character set
- never duplicate assets just because the source character belongs to another script with the same pronunciation

Possible placement:

- `backend/src/course_builder/workflows/` only if you want DBOS orchestration reuse
- otherwise a dedicated domain workflow outside course build is cleaner

Recommendation: keep it outside the course build lifecycle, but reuse the same infra helpers and shared audio storage.

## Suggested Rollout Phases

### Phase 1: data and planning

- add kana catalog tables and migrations
- add per-user kana progress tables
- add kana lesson and kana lesson item tables
- define syllabus ordering and exposure targets

### Phase 2: audio

- extract shared audio hashing/reuse helpers
- add kana audio asset generation workflow
- add kana audio serving route

### Phase 3: backend lesson engine

- add kana overview service
- add continue-learning planner
- add kana item selection heuristics
- add kana submit scoring and progress updates

### Phase 4: frontend

- add kana overview page
- add kana lesson session flow
- add progress visualization
- connect using generated API client only

### Phase 5: tuning

- tune distractor quality
- tune target exposures by group
- tune mastery thresholds
- review lesson boredom/repetition metrics

## Remaining Questions

No open product questions remain in the current v1 plan.

## Recommendation Summary

Recommended v1 decisions:

- separate kana track from the main course path
- one combined hiragana/katakana queue
- exposure target `6`
- hiragana-first, then gradual katakana mix
- voiced kana introduced base-first
- separate kana backend/domain model
- separate kana API schemas
- separate kana audio workflow, not tied to course build execution
- shared audio storage keyed by normalized spoken text
- no duplicate audio generation for hiragana/katakana pairs with identical pronunciation
- explicit syllabus order with deterministic lesson planning plus controlled variation
