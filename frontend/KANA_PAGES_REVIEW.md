# Kana overview & lesson pages — frontend review

This report maps the **kana** UI (`/kana`, `/kana/lesson/$lessonId`) and related modules against the expectations in [`GUIDE.md`](./GUIDE.md) (Vite + React + TanStack Router + TanStack Query + generated API client + Tailwind + Biome + Vitest).

## Scope (files reviewed)

| Area | Primary files |
|------|----------------|
| Overview page | `src/pages/kana-page.tsx` |
| Lesson page | `src/pages/kana-lesson-page.tsx`, `src/pages/kana-lesson-feedback.tsx` |
| Feature layer | `src/features/kana/queries.ts`, `src/features/kana/model.ts`, `src/features/kana/use-kana-lesson-session.ts`, `src/features/kana/audio-cache.ts` |
| Routing | `src/app/router.tsx` (`kanaRoute`, `kanaLessonRoute`) |
| Shared lesson UI | `src/pages/lesson/session-model.ts`, `src/pages/lesson/shortcuts.ts`, `src/pages/lesson/ui-constants.ts` |

---

## Alignment with `GUIDE.md`

### TanStack Query (keys, options, mutations)

- **Key factory**: `kanaKeys.overview` and `kanaKeys.lesson(lessonId)` in `queries.ts` are array-based and serializable, matching the guide’s “public interface” pattern.
- **Query function**: `kanaOverviewQueryOptions` passes `{ signal }` through to the generated API call — consistent with the guide’s cancellation guidance.
- **Mutations → cache**: `useContinueKanaLearning` uses `onSettled` to `invalidateQueries({ queryKey: kanaKeys.overview })`, so continue/planning reconciles server state with the cache.
- **User-critical freshness**: `staleTime: 0` and `refetchOnMount: "always"` on the overview are documented in-code as required for `is_next_lesson_new` accuracy — this matches the guide’s idea of tuning refetch for time-sensitive, user-visible state.

### Router + Query coordination

- **`/kana` loader**: Invalidates `kanaKeys.overview` then `ensureQueryData(kanaOverviewQueryOptions())`, so returning from a lesson does not silently reuse a stale overview — aligned with “pick a primary cache (Query) and coordinate loaders to prefetch/ensure.”
- **`/kana/lesson/$lessonId`**: No loader; the lesson page invalidates overview and `ensureQueryData` for prefetch — acceptable, though it duplicates the “fresh overview” concern in two places (loader + lesson mount).

### TypeScript & API boundaries

- Overview view-model helpers (`masteryPercent`, tile classes, tappability) consume **generated** `KanaCharacterProgress` / `KanaOverviewResponse` types from `shared/api/generated` — no parallel hand-written DTOs.
- API access goes through `shared/api` wrappers + generated client — consistent with the guide’s layering (no ad-hoc fetch in random components for these flows).

### Effects vs purity

- **`kana-page`**: Effects are used for **audio teardown**, **catalog prefetch** after overview loads, and **unmount cleanup** — these are external-system sync (browser audio + network cache), not derived UI state. Renders remain a function of query data + refs.
- **`kana-lesson-page`**: Multiple `useEffect` hooks drive **HTMLAudioElement** playback, **debounced autoplay after motion** (`kanaAutoplayDelayMs` + `QUICK_TRANSITION`), and **item-level audio prefetch**. That is a lot of effect surface area, but it is largely justified as synchronization with the audio subsystem and animation timing rather than “compute something we could derive during render.”

### Motion & accessibility

- **`useReducedMotion`** gates exit/initial offsets and zeroes transition duration when the user prefers reduced motion; autoplay delay becomes `0` in that case — consistent with the guide’s motion accessibility expectations.

### Icons & Tailwind

- **Lucide**: Icons are imported per-component (`Volume2`, etc.), preserving tree-shaking.
- **Tailwind**: Classes live in TSX under existing content globs; no structural conflict with the guide.

---

## Architecture summary

1. **Overview**: `useKanaOverviewQuery` → grid built via `buildKanaGroupRows` → per-cell `kanaOverviewTileClassName` + `isKanaOverviewTileTappable` → optional playback via `getKanaAudioBlob` + in-memory cache (`audio-cache.ts`).
2. **Continue / start**: Primary CTA calls `handleContinue`: if `current_lesson_id` exists, **refetch** then navigate; else `continue` mutation, refetch, navigate.
3. **Lesson session**: `useKanaLessonSession` holds a **local queue** (main line + review), loads items with `loadKanaLessonItem(lessonId, cursor)`, submits single-item checks and final batch submit via `useSubmitKanaLesson`, and invalidates `kanaKeys.overview` on successful completion.

---

## Strengths

- **Clear separation** between API/query wiring (`queries.ts`), pure view-model (`model.ts`), and session state machine (`use-kana-lesson-session.ts`).
- **Defensive concurrency** in session init (`cancelled`, `lessonIdRef`, `loadAttemptRef`) when the route param or retry count changes mid-flight.
- **Keyboard UX** (Space for check / continue) reuses shared lesson shortcut helpers and avoids stealing Space from unrelated controls.
- **Audio**: Centralized blob cache + bounded concurrency for overview prefetch reduces repeated authenticated fetches.

---

## Gaps, risks, and improvement opportunities

### 1. Copy vs behavior on the overview hero (UX inconsistency)

The hero text still says (in essence) “tap a character to hear it,” but tiles are **disabled** unless the character is learning, mastered, or `is_next_lesson_new`. Users who cannot tap gray “new” tiles may find the headline misleading. Aligning the string with `isKanaOverviewTileTappable` semantics would match both product intent and the backend contract described in `model.ts` comments.

### 2. Lesson item loading without `AbortSignal`

`loadKanaLessonItem` and the `nextItemMutation` path do not wire **query/mutation cancellation** to the underlying fetch. If the user navigates away quickly, in-flight requests may still complete (usually harmless but contrary to the guide’s “pass signal when supported” ideal). Low priority unless profiling shows wasted work.

### 3. Feature vs `pages/lesson` dependency

`use-kana-lesson-session.ts` imports progress helpers from `pages/lesson/session-model.ts`. The guide prefers **`features/<feature>`** as the domain home. This works but creates a **dependency from feature → page-layer** utilities; long-term, moving shared session math to `shared/` or `features/lesson/` would clarify boundaries.

### 4. Density of `useEffect` on `kana-lesson-page`

The page is correct but **effect-heavy**. Any future change should watch for:

- Double invocation in React 18 Strict Mode (timeouts/audio are cleaned up — current pattern is mostly safe).
- Overlap between **manual** `playAudio` (e.g. option click) and **scheduled** autoplay when navigating items quickly.

### 5. Redundant overview refresh paths (intentional but layered)

Overview freshness is enforced by: overview query options, `/kana` loader invalidation, lesson entry invalidation, continue mutation invalidation, and explicit refetch in `handleContinue`. This is **defensive** against stale UI; if network chatter ever becomes an issue, consider consolidating rules (e.g. document a single “source of truth” for when overview must refetch) without changing product behavior.

### 6. Error surfacing

- Overview: errors render inline — reasonable.
- Lesson init: retry path exists; good.
- `handleCheck` catches mutation errors generically; `checkAnswerError` surfaces `submitMutation.error` — consistent.

---

## Testing note (`GUIDE.md` quality gates)

`model.ts` helpers (`kanaOverviewTileClassName`, `isKanaOverviewTileTappable`) have unit coverage in `src/test/kana/model.test.ts`. Session and page integration remain primarily manual or indirect; adding focused tests for queue/advance behavior would further match the repo’s “non-negotiable” test posture for complex hooks.

---

## Summary

The kana flows **largely follow** `GUIDE.md`: Query-owned cache with router-coordinated prefetch, stable keys, mutation invalidation, generated types, reduced-motion-aware motion, and effects scoped to **browser/audio** concerns. The main follow-ups are **product copy accuracy** on the overview, optional **abort/cancellation** for lesson item fetches, and **structural tidiness** (feature ↔ shared lesson session helpers) if the team wants stricter module layering.
