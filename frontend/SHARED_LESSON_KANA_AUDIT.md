# Shared lesson + kana lesson — extraction audit

This document reviews **main course lesson** (`src/pages/lesson/`) and **kana lesson** (`src/pages/kana-lesson-page.tsx`, `src/features/kana/*`, `src/pages/kana-lesson-feedback.tsx`) to list what is reasonable to move into **`src/shared/lesson/`** (or equivalent). It is a **findings-only** pass for a follow-up implementation PR.

## Scope reviewed

| Area | Paths |
|------|--------|
| Main lesson UI + runtime | `src/pages/lesson/*` (especially `index.tsx`, `use-session.ts`, `session-*.ts`, `feedback-tray`, `top-bar`, `leave-dialog`, `complete-screen`, `bottom-zone`, `ui-constants`, `shortcuts`, `typography`) |
| Kana lesson | `src/pages/kana-lesson-page.tsx`, `src/pages/kana-lesson-feedback.tsx`, `src/features/kana/use-kana-lesson-session.ts`, `src/features/kana/use-kana-lesson-page-audio.ts` |
| Kana overview (uses lesson chrome) | `src/pages/kana-page.tsx` (imports `PRIMARY_BUTTON_CLASS` from lesson ui-constants) |

## Dependency problem today

- **`features/kana/`** imports **`pages/lesson/`** for `session-model`, `session-types`, and `shortcuts` — an inverted layer (features should not depend on route folders per `GUIDE.md` / common frontend layering).
- **`pages/kana-lesson-*`** import **`pages/lesson/`** for chrome (`LeaveLessonDialog`, `LessonTopBar`, `ui-constants`, `session-types`, `typography`) — acceptable for pages, but a **`shared/lesson/`** home makes both kana and main lesson depend on one neutral module.

---

## Tier A — Move with high confidence

These modules are already **imported by both flows** or are **pure utilities** with no main-lesson-only coupling.

| Item | Current location | Notes |
|------|------------------|--------|
| **Queue / progress math** | `pages/lesson/session-model.ts` | Used by `use-session.ts` and `use-kana-lesson-session.ts` (`lessonTotalCount`, `lessonCurrentIndex`, `topBarCompletedItemCount`, `remainingReviewCount`, `hasMoreMainItemsToLoad`, `progressBarCssWidth`). `buildOrderedCompletionAnswers` is tied to `LessonItemResponse` + main completion payload — keep next to main lesson **or** split file: `session-model-core.ts` (shared) + `session-model-completion.ts` (main only). |
| **Feedback shape** | `pages/lesson/session-types.ts` | `FeedbackState` is shared (main feedback tray + kana feedback + both session hooks). **Unify `QueueEntry`**: kana re-declares the same `{ itemId, source }` inline in `use-kana-lesson-session.ts` — should import one type. |
| **Keyboard / Space handling helpers** | `pages/lesson/shortcuts.ts` | `LESSON_ANSWER_CONTROL`, `isLessonAnswerControlTarget`, `isSpaceTargetInsideInteractiveControl` — shared; kana lesson uses the same semantics. |
| **Motion + button tokens** | `pages/lesson/ui-constants.ts` | `QUICK_TRANSITION`, `FAST_TRANSITION`, `PRIMARY_BUTTON_CLASS`, `SECONDARY_BUTTON_CLASS` — used by main lesson, kana lesson, kana overview, dialogs. Natural **`shared/lesson/ui-constants.ts`**. |
| **Answer typography helper** | `pages/lesson/typography.ts` | `optionTypographyClass` (and likely `promptTypographyClass`) are generic JP/Latin class selection — used by both feedback trays and main prompt styling. |

## Tier B — Shared UI components (move as-is or thin wrappers)

| Item | Current location | Notes |
|------|------------------|--------|
| **Leave confirmation** | `pages/lesson/leave-dialog.tsx` | Already reused by kana lesson; should live under **`shared/lesson/`** so pages only wire navigation callbacks. Copy is path-centric (“return to the path”) — consider **props for title/description** if kana should say “kana overview” instead (optional polish). |
| **Top bar** | `pages/lesson/top-bar.tsx` | Reused by kana; depends on `session-model` (`progressBarCssWidth`) and `ui-constants` (`FAST_TRANSITION`). After moving deps, co-locate or import from `shared/lesson`. |

## Tier C — Strong merge candidates (duplication / parallel structure)

### 1. Feedback trays (`LessonFeedbackTray` vs `KanaLessonFeedbackTray`)

- **Overlap:** Same card chrome (border tones, ✓/!, “Correct”/“Incorrect”, “Nice. Keep going.”, continue button, `continueError`, loading state).
- **Kana-only:** Incorrect branch for `kana_to_audio_choice` — “Correct sound” + `Volume2` + optional replay; otherwise shows “Correct answer:” + typography like main lesson.
- **Reasonable approach:** One **`shared/lesson/feedback-tray.tsx`** with optional render props or optional props  
  `incorrectExtra?: ReactNode` / `variant: "default" | "kana-audio"`  
  so main lesson stays one line, kana passes the audio row. Avoid three copies of the same layout.

### 2. Page shell class string

- `LESSON_PAGE_SHELL_CLASS` in `pages/lesson/index.tsx` and `KANA_PAGE_SHELL_CLASS` in `kana-lesson-page.tsx` are the **same** full-screen lesson shell string.
- **Reasonable:** `shared/lesson/layout.ts` or `ui-constants.ts` exporting `LESSON_PAGE_SHELL_CLASS` once.

### 3. Framer “item card” motion block

- Both pages wrap the active item in **`AnimatePresence` + `motion.section`** with **`QUICK_TRANSITION`**, reduced-motion guards, `key={currentItem.item_id}`, similar border/shadow classes (minor class differences).
- **Reasonable:** Optional **`LessonItemMotionSection`** presentational wrapper (props: `itemId`, `children`, optional `className`) to avoid drift — **low priority** if you prefer fewer abstractions.

### 4. Space-bar lesson shortcut (window `keydown`)

- **`use-session.ts`** and **`use-kana-lesson-session.ts`** implement the same pattern: Space → continue if feedback, else Check if allowed; guards for dialog, finished lesson, pending mutations, interactive targets.
- **Reasonable:** Extract **`useLessonSpaceToAct`** (name TBD) in `shared/lesson/use-space-to-act.ts` taking stable refs + booleans (`canCheck`, `hasFeedback`, `isLeaveDialogOpen`, …) and callbacks (`advanceQueue`, `handleCheck`). Reduces duplicate bugs when one hook changes behavior.

### 5. “Sprint complete” completion screen

- **Main:** `LessonCompleteScreen` — headline + stats line + **two stat cards** + “Back to path”.
- **Kana:** inline completion in `kana-lesson-page.tsx` — same headline logic (`mistakeCount === 0 ? "Clean finish." : "Every item solved."`), same stats sentence, **no stat cards**, button “Back to kana”.
- **Reasonable:** Shared **`LessonSprintCompleteBody`** props: `correctCount`, `mistakeCount`, `completionProgressState`, `accentLabel` (“Speedrulingo sprint” vs “Kana sprint”), `primaryAction` (button node or label + `onClick`). Main lesson keeps extra cards as optional slot or separate wrapper.

### 6. Bottom check / feedback zone motion

- **`LessonBottomZone`** animates feedback vs check with the same `AnimatePresence`/`motion.div`/`QUICK_TRANSITION` pattern as **`kana-lesson-page`** (inline).
- **Reasonable:** Reuse or extract a thin **`LessonActionOrFeedbackZone`** that wraps the same motion keys — kana might pass `KanaLessonFeedbackTray` vs main passes `LessonFeedbackTray` as children. **Only worth it** after Tier C.1 tray unification to avoid abstraction churn.

---

## Tier D — Similar patterns but keep separate (or share only tiny helpers)

| Topic | Why not a big shared module |
|-------|-----------------------------|
| **Session hooks** | `useLessonSession` vs `useKanaLessonSession` differ in API types (`LessonItemResponse` vs `KanaLessonItemResponse`), mutations (`lesson-runner` vs kana API), completion (`completeLesson` vs batch submit), state machines (`session-state` / `session-transitions` vs kana-local state). **Do not merge** into one mega-hook; at most share Tier C.4 keyboard helper + Tier A math/types. |
| **Completion answer ordering** | `buildOrderedCompletionAnswers` in `session-model.ts` is **main-lesson-specific** (user answer strings). Kana uses **`orderedCompletionAnswers`** with `optionId` in `use-kana-lesson-session.ts`. Optional: two small functions in **`shared/lesson/ordered-answers.ts`** with clear names if you want them out of `session-model`. |
| **Audio playback** | Main lesson builds object URLs from sentence/token URLs in the page; kana uses **`features/kana/audio-cache`** + catalog prefetch. **Different fetch/auth/cache** — share only generic **`resetObjectUrlAudio`**-style helper if you extract a tiny util, not the full pipeline. |
| **Initialization / errors** | Both have loading, init error + retry, empty `!currentItem` — **similar UX**, different copy. Optional small **`LessonErrorPanel`** / **`LessonLoadingPanel`** if duplication grows. |

---

## Suggested target shape (for the implementation pass)

```
src/shared/lesson/
  session-model.ts          # Tier A (+ optional split for main-only completion)
  session-types.ts          # FeedbackState, QueueEntry, …
  shortcuts.ts
  ui-constants.ts
  typography.ts
  leave-dialog.tsx          # Tier B
  top-bar.tsx               # Tier B
  feedback-tray.tsx         # Tier C.1 (unified or base + kana extension)
  use-space-to-act.ts       # Tier C.4 (optional)
  layout.ts                 # Tier C.2 shell class
```

`pages/lesson/index.tsx` and `pages/kana-lesson-page.tsx` become **thin composers** importing from `shared/lesson`. `features/kana` imports **`shared/lesson`** instead of **`pages/lesson`**.

Tests: move `src/test/lesson/session-model.test.ts` → `src/test/shared/lesson/session-model.test.ts` (or co-locate), update imports.

---

## Risks / sequencing

1. **Barrel exports:** Prefer **direct imports** from small files (per project preference) unless you add `shared/lesson/index.ts` with explicit re-exports only.
2. **Copy in `LeaveLessonDialog`:** Path-specific wording may need props before kana feels native.
3. **Feedback tray merge:** Do the shared visual core first; kana audio row as an optional branch to avoid regressions.
4. **Regression checks:** Both flows rely on Space + Leave + progress bar — manual smoke on `/lesson/...` and `/kana/lesson/...` after moves.

---

## Summary

| Tier | Action |
|------|--------|
| **A** | Move **`session-model`** (split if needed), **`session-types`**, **`shortcuts`**, **`ui-constants`**, **`typography`**; fix kana **`QueueEntry`** duplication. |
| **B** | Move **`LeaveLessonDialog`**, **`LessonTopBar`** to **`shared/lesson`**. |
| **C** | Consider unified **feedback tray**, **shell class**, optional **Space hook**, **completion screen** shared body, optional **motion wrapper**. |
| **D** | Keep **session hooks** and **audio stacks** separate; only small helpers if clearly valuable. |

This list is the intended checklist for the follow-up extraction PR.
