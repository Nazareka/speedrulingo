# `src/` layout

Canonical boundaries are documented in **[`STRUCTURE.md`](../STRUCTURE.md)** (layers, nouns vs verbs, import rules).

| Area | Role |
| --- | --- |
| **`app/`** | Providers, router assembly, global error UI. |
| **`pages/`** | Thin route shells (`*-page.tsx`). |
| **`widgets/`** | Optional composed sections (e.g. app shell). |
| **`features/<area>/`** | Screens, orchestration, mutations — user capabilities. |
| **`entities/<noun>/`** | Domain types, pure derivations, noun-scoped reads. |
| **`shared/`** | API client, auth token + session queries, env, tokens, global styles. |
| **`shared/api/generated/`** | OpenAPI output — generated only. |
| **`test/`** | Vitest setup, `test-utils`, shared test query client. |

**Imports:** Enforced by dependency-cruiser (`npm run check:imports`). See **`STRUCTURE.md`** for the matrix and exceptions.
