# Frontend `src/` structure

Single source of truth for how the Speedrulingo web app is organized. **Folder names matter less than import direction:** lower layers must not depend on higher layers.

---

## Layer model

| Layer | Responsibility | Imports from |
| --- | --- | --- |
| **`app/`** | Bootstrap: providers, router factory, route modules, global error UI | `widgets/`, `pages/`, `features/`, `entities/`, `shared/` |
| **`pages/`** | Route adapters: params, search, compose a screen | `features/`, `entities/`, `shared/` only |
| **`widgets/`** | Large composed sections reused across routes (not a full screen, not a “verb”) | `features/`, `entities/`, `shared/` only |
| **`features/`** | User-visible capabilities: screens, orchestration, mutations, feature state | `entities/`, `shared/` only |
| **`entities/`** | Domain **nouns**: types, pure derivations over API shapes, noun-scoped read queries / tiny UI | `shared/` and other `entities/` |
| **`shared/`** | Infrastructure and generic primitives | `shared/` only |
| **`test/`** | Vitest setup and shared test helpers (excluded from dependency-cruiser) | — |

**One-line roles**

- **`app`** — wires the running application (router + providers + global shell hooks).
- **`pages`** — answers “which route is this?” by composing a feature screen.
- **`widgets`** — answers “which reusable chrome block?” (e.g. app frame with nav).
- **`features`** — answers “what can the user do here?” (verbs: learn, pick a unit, log in).
- **`entities`** — answers “what domain things exist?” (nouns: path selection, lesson session shape, unit).
- **`shared`** — answers “what could any app reuse?” (HTTP client, tokens, motion tokens).

---

## Dependency rules

These are enforced by **dependency-cruiser** (`.dependency-cruiser.cjs`), run via **`npm run check:imports`** and **`npm run verify`**.

1. **`shared`** must not import `entities`, `features`, `widgets`, `pages`, or `app`.
2. **`entities`** must not import `features`, `widgets`, `pages`, or `app`.
3. **`features`** must not import `widgets`, `pages`, or `app`.
4. **`widgets`** must not import `pages` or `app`.
5. **`pages`** must not import `app` or `widgets`.

**Sibling features:** a feature must not import another feature’s tree, **except** the documented case: **`features/kana` may import `features/lesson`** for shared lesson chrome (layout, shortcuts, feedback shell, top bar). For shared **types and pure logic** used by both, prefer **`entities/lesson`** (and related entity modules).

**Invalidate remote caches** using stable keys from **`shared/auth/session-keys`**, **`entities/path/query-keys`**, or feature **`api/`** modules — not ad hoc strings scattered in UI.

---

## Expected `src/` layout

```
src/
  main.tsx              # Vite entry (next to app/ is fine)
  app/
    providers.tsx
    route-error-fallback.tsx
    router/             # root-route, auth-routes, learning-routes, account-routes, index (createRouter)
  pages/                # *-page.tsx — thin route shells
  widgets/              # optional; e.g. app-shell/
  features/
    <area>/
      api/              # TanStack Query: queries, mutations, keys re-export if needed
      model/            # hooks, view-model, session orchestration
      ui/               # feature components
      lib/              # feature-only helpers (e.g. lesson layout + shortcuts)
      *-screen.tsx      # composed route body, or under ui/
  entities/
    <noun>/
      *.ts              # model, query-keys, unit-lessons, etc.
  shared/
    api/                # generated OpenAPI client + handwritten client wrapper
    auth/               # token-store, session-keys, session queries
    lib/
    ui/                 # layout primitives, tokens/
    styles/
  test/                 # setup, test-utils, shared test query client
```

Smaller features may stay **flat** (`features/kanji/`) until they grow; larger ones use **`api/` / `model/` / `ui/`** consistently (**`lesson`**, **`path`**, **`kana`**).

---

## `entities/` vs `features/` (nouns vs verbs)

| | **`entities/<noun>/`** | **`features/<area>/`** |
| --- | --- | --- |
| **Holds** | Stable domain “things”: types, pure functions over DTOs, path/lesson **read** keys, small presentational pieces tied to that noun | User **actions** and **screens**: mutations, multi-step flows, composed UI |
| **May include** | Read-only React Query hooks for that noun | Session orchestration, forms, route-driven state |

**Examples (this repo)**

- **`entities/path/model.ts`** — `PathSelection`, slides, normalization over `PathResponse`.
- **`entities/path/unit-lessons.ts`** — lesson ordering, progress width string, entry lesson id (pure).
- **`entities/path/query-keys.ts`** — TanStack Query key roots for path data (invalidation from any layer).
- **`entities/lesson/session-types.ts`**, **`session-model.ts`**, **`session-completion.ts`** — shared runtime shape and math for main lesson + kana.
- **`entities/unit/queries.ts`**, **`unit-guide-card.tsx`** — unit as a reusable noun.

**Feature-only view-model** (circle-chain rows, picker-specific VM, carousel transition state) stays under **`features/path/model/`** (or similar), not in **`entities/`**.

---

## `pages/` vs screens

- There is **no** top-level `screens/` folder.
- A **screen** is the composed route body: typically **`*Screen.tsx`** under **`features/<area>/`** (or **`features/<area>/ui/`**).
- A **page** only wires the router (params, search, navigation) and renders the screen.

---

## `shared/` discipline

- **No** product workflow rules (unlock logic, scoring business rules) unless they are truly generic.
- **`shared/api/generated/`** — OpenAPI output only; never hand-edit.
- **`shared/api/client/`** and **`shared/api/index.ts`** — app-owned HTTP configuration, headers, **`requireResponseData`**, re-exports.
- **`shared/auth/token-store.ts`** — persistence for the API client; not React Query.
- **`shared/auth/session-keys.ts`** — stable key roots for **`me`** and **current course** (import when invalidating after auth).
- **`shared/auth/session.ts`** — **`me` / `current-course`** query option builders and thin **`useQuery`** hooks only. **Do not** grow it with logout orchestration, permission matrices, profile business rules, or redirect policy — put those in **`features/`** or route code.
- **`shared/ui/tokens/`** — shared **motion**, **button**, **form** class strings; avoid turning it into a dump of one-off feature classes.

---

## `app/` and router

- **`app/router/index.tsx`** — **`createRouter`**, **`AppRouter`** export; keep it thin.
- Route definitions split across **`root-route`**, **`auth-routes`**, **`learning-routes`**, **`account-routes`** as needed.
- **`widgets/app-shell/app-frame.tsx`** holds global navigation chrome; **`app/route-error-fallback.tsx`** handles root error UI.

---

## Tests

- Place unit tests **next to** the code under **`features/`** and **`entities/`**.
- Keep **`src/test/`** for **`setup.ts`**, **`test-utils`**, and shared test doubles (e.g. **`create-test-query-client`**).

---

## Anti-patterns

1. **`shared/`** as a junk drawer for “stuff two features use” — extract a noun to **`entities/`** or keep logic in the feature that owns the workflow.
2. **Fat `pages/`** with API calls and domain rules — push down to **`features/`** and **`entities/`**.
3. **Features named by tech** (`hooks/`, `modals/` at the top level) — name by capability (`lesson/`, `auth/`).
4. **Bypassing import rules** — update **`.dependency-cruiser.cjs`** if you add a new top-level feature directory or a new allowed exception.

---

## Related tooling

| Command | Purpose |
| --- | --- |
| **`npm run check:imports`** | dependency-cruiser against `src/` |
| **`npm run verify`** | Biome + TypeScript + import check + tests |
