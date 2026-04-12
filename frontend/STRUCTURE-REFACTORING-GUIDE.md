# Frontend alignment with `STRUCTURE.md`

This document turns the norms in [`STRUCTURE.md`](./STRUCTURE.md) into a **practical refactor roadmap** for this repo. It describes where the codebase diverges today and how to converge without a big-bang rewrite.

The guiding idea from `STRUCTURE.md`:

| Layer | One-sentence role |
| --- | --- |
| **app** | Bootstraps and wires the application |
| **pages** | Route screens that compose features/widgets/entities |
| **widgets** *(optional)* | Large reusable screen sections (not a full route, not a single “verb”) |
| **features** | User-visible capabilities and business actions (“verbs”) |
| **entities** *(optional)* | Domain nouns (types, selectors, read models, small display pieces) |
| **shared** | Generic, business-agnostic primitives |
| **test** | Shared test infrastructure only |

Dependency direction (from `STRUCTURE.md`): **shared → nothing outside shared; entities → shared; features → entities + shared; pages → everything below pages; app → anywhere.** Reverse imports are the main thing to prevent.

---

## Current state (snapshot)

What already matches the doc well:

- **Top-level buckets** exist: `src/app/`, `src/pages/`, `src/features/`, `src/shared/`, `src/test/`.
- **Main course lesson** logic largely lives under `src/features/lesson/` (session, exercises, queries), with `src/pages/lesson/` acting as a route shell—aligned with “pages compose.”
- **Generated API** and HTTP helpers live under `src/shared/api/`, consistent with “API client base” in shared.

Notable gaps vs the doc:

1. **Entrypoint placement** — `src/main.tsx` sits next to `app/` rather than inside `app/` (as in the `STRUCTURE.md` examples). Functionally fine; it is a small inconsistency with the illustrated tree.

2. **`app/router.tsx` is doing a lot** — Besides router construction, it includes **global chrome** (nav, active states, lesson-mode layout behavior) and **data wiring** (e.g. prefetch/refresh helpers from features). `STRUCTURE.md` reserves `app/` for shell wiring and warns against “page-specific UI” and heavy domain orchestration living there. Today this file blurs **app shell** vs **product navigation**.

3. **`shared/lesson/` is domain-heavy** — There is a large `src/shared/lesson/` tree (top bar, leave dialog, feedback tray, session model helpers, lesson typography tokens, etc.). Per `STRUCTURE.md`, **shared should not be the home for lesson vocabulary** unless the piece is genuinely generic. Much of this is **product UI and lesson domain**, not Radix wrappers or `cn()`.

4. **`pages/path/` mixes route composition with domain logic** — Files such as `model.ts`, `state.ts`, `lesson-derive.ts`, `lesson-circle-chain-vm.ts`, and a very large `unit-carousel.tsx` embed **path/course selection behavior and view-model logic** next to the route. That belongs in **features** (actions/use cases) and/or **entities** (course/unit/lesson shapes and selectors), not in `pages/`.

5. **Flat vs folder routes** — Some routes are folders (`pages/lesson/`, `pages/path/`); others are single files at `pages/` root (`kana-lesson-page.tsx`, `login-page.tsx`, …). The doc’s examples favor **one folder per route** with a clear entry (e.g. `pages/lesson/ui/lesson-page.tsx`). Inconsistency makes it harder to enforce “pages stay thin.”

6. **Feature folders are not structured uniformly** — `STRUCTURE.md` suggests optional `ui/`, `model/`, `api/` inside a feature. Here, features are flatter (`queries.ts`, hooks at top level). Not wrong, but **conventions are undocumented**, so new code drifts.

7. **Tests** — There is good coverage under `src/test/` (e.g. `test/path/`, `test/shared/lesson/`). `STRUCTURE.md` prefers **unit tests next to implementation** and **`test/` only for shared harness**. Migrating gradually would match the doc.

8. **Import boundaries are not automated** — The doc recommends ESLint (or equivalent) to enforce layer rules. There is no such guardrail in-repo yet, so structure relies on review discipline only.

---

## Target architecture (incremental)

You do **not** need every optional folder on day one. A sensible end state for a growing app:

- **Option A** (minimal): `app`, `pages`, `features`, `shared`, `test` — already mostly in place; focus on **draining misplaced code** and **enforcing imports**.
- **Option B** (scalable, from `STRUCTURE.md`): add **`entities/`** when the same domain objects appear in many features, and **`widgets/`** when route files grow large compositional JSX blocks.

Recommended direction for *this* codebase:

1. Introduce **`widgets/`** only for **cross-route lesson chrome** shared by main lesson + kana lesson (today split across `features/*` and `shared/lesson/`). That matches “large reusable screen sections.”
2. Introduce **`entities/`** when you extract **course / unit / lesson / path** read models and types used by `features/path`, `features/units`, and lesson flows—matching “entities = nouns, features = verbs.”

---

## Phased refactor plan

Work in small PRs. Order is dependency-aware: **shared cleanup and feature extraction before** tightening `app/` and **enforcing** boundaries.

### Phase 1 — Clarify `shared/lesson` (highest leverage)

**Goal:** `shared/` should not read like a second “lesson feature.”

- Audit each file under `src/shared/lesson/`.
- **Move** into `src/features/lesson/` (or `src/widgets/lesson-shell/` if shared by multiple lesson routes) anything that encodes **lesson UX, copy, or session rules** (e.g. feedback tray, top bar, leave dialog, sprint summary, motion sections tied to lesson pacing).
- **Keep in `shared/`** only what is **truly generic**: e.g. tokenized CSS variable names if they are app-wide design tokens, or a hook like `useReducedMotion` wrapper—if it has **no lesson semantics**.
- **Session math/helpers** (`session-model.ts`, `session-types.ts`, etc.): if they describe **lesson progression** as a domain concept, prefer **`entities/lesson`** or **`features/lesson/model`** per `STRUCTURE.md`; avoid leaving domain vocabulary in `shared/`.

Update imports and tests in the same PRs to avoid churn.

### Phase 2 — Thin `pages/path/` (move nouns vs verbs)

**Goal:** `PathPage` reads as “compose path feature + units + shared layout,” not “implement the path.”

- Move **pure data derivations** (`model.ts`, `lesson-derive.ts`, `lesson-circle-chain-vm.ts`) to:
  - **`features/path/model/`** or **`entities/course/` + `entities/unit/`** depending on reuse.
- Move **React state orchestration** (`state.ts`, hooks that tie queries to UI) to **`features/path/`** (e.g. `use-path-page.ts`).
- Keep under **`pages/path/`** only:
  - route-specific composition,
  - loading/error shells tied to the route,
  - wiring params/search if any.

Large presentational chunks (**`unit-carousel.tsx`**, **`lesson-circle-chain.tsx`**) should become **`widgets/path-*`** or live under **`features/path/ui/`** if they are not reused—still out of `pages/` if they are hundreds of lines of UI logic.

### Phase 3 — Thin route pages for kana, auth, account, kanji

**Goal:** Same rule as lesson: **params + compose + minimal glue.**

- Split **`kana-lesson-page.tsx`** (and similar) so **audio orchestration** and **session** stay in **`features/kana/`**, and the page mostly maps route → feature components.
- Align naming: either **folder per route** (`pages/kana-lesson/index.tsx`) or document the flat-file convention—pick one.

### Phase 4 — Split `app/router.tsx`

**Goal:** Router file defines **routes and providers’ context**; global nav/layout lives elsewhere.

- Extract **`AppFrame`** (nav, active tab styling, lesson-mode detection) to e.g. **`widgets/app-shell/`** or **`pages/_layout/`** pattern your router supports, imported by a **root layout route** component.
- Keep **route definitions** and **redirect/auth guards** in `app/` or colocated route modules, but avoid growing **product-specific JSX** inside `app/` indefinitely.

### Phase 5 — Optional: `entities/` rollout

Add **`src/entities/`** when the same types/selectors appear in **path**, **lesson**, and **units**:

- `entities/lesson/` — IDs, labels, progress helpers, selectors.
- `entities/course/` / `entities/unit/` — structures returned by path API, section/unit selection helpers.

**Features** import entities; **pages** should not implement selectors.

### Phase 6 — Tests and tooling

- **Co-locate tests** with `features/*` and `entities/*` as you touch files; leave **`src/test/`** for `setup`, `test-utils`, MSW, fixtures.
- Add **import boundary rules** (e.g. `eslint-plugin-import` with zones, or `eslint-plugin-boundaries`, or Biome if/when supported) implementing the matrix from `STRUCTURE.md`.
- Extend **`vitest.config.ts`** coverage paths when files move (as done for `features/lesson`).

---

## Dependency rules (enforcement checklist)

When automation is in place, encode at least:

| From → To | Allowed? |
| --- | --- |
| `shared` → `features` / `pages` / `app` | **No** |
| `entities` → `features` / `pages` | **No** |
| `features` → `pages` / `app` | **No** |
| `widgets` → `pages` / `app` | **No** |

`app` may import anything; **`pages` must not be imported** by lower layers for reuse as components.

---

## How to know you are done (per area)

- **`app/`**: Entry, providers, router factory, global error boundary—**no** product navigation megacomponent unless you explicitly accept it as temporary.
- **`pages/`**: Mostly **params, loaders, composition**; no large DTO munging or unlock rules.
- **`features/`**: Named by **user capability**; houses mutations, session hooks, validation—**not** folders named `hooks` or `modals` at the top level unless they are subfolders *inside* a feature.
- **`shared/`**: Could be copied to another app with minimal renaming; **no lesson/course/path business rules**.
- **`test/`**: Harness and cross-cutting mocks only; **feature tests** live next to features.

---

## Relationship to `STRUCTURE.md`

This guide **does not replace** [`STRUCTURE.md`](./STRUCTURE.md). Use `STRUCTURE.md` for principles and layer definitions; use **this file** for **repo-specific gaps and a sequenced migration**. Update this guide when major moves (e.g. `entities/`, `widgets/`) land so it stays honest.
