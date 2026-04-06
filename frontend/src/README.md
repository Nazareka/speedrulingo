# `src/` layout

Canonical boundaries (see [GUIDE.md](../GUIDE.md) and [APPLYING-GUIDE-TO-SRC.md](../APPLYING-GUIDE-TO-SRC.md)):

| Area | Role |
|------|------|
| **`app/`** | App shell: providers, router entry, layout. |
| **`pages/`** | Route-level screens (compose features + shared UI). |
| **`features/<domain>/`** | Domain logic: TanStack Query hooks/mutations, feature components. No generated API edits. |
| **`shared/`** | Cross-cutting: API client config + HTTP helpers (`shared/api/`), auth token store, session queries, **`shared/lib/query-client.ts`** (singleton `queryClient` for React Query + TanStack Router loaders), UI primitives, global styles. |
| **`shared/api/generated/`** | Hey API OpenAPI output — **generated only**, never hand-edited. |
| **`test/`** | Vitest helpers: `createTestQueryClient`, `TestProviders` / `renderWithProviders` (Query + Motion; use `RouterProvider` + `context.queryClient` for router tests). `setup.ts` loads Testing Library matchers. |

**Imports:** Prefer feature → `shared`, and `pages` → `features` / `shared`. Avoid `features` importing from `pages`.
