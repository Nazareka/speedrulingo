# Production-grade coding guide for a Vite + React + TypeScript code agent

This guide is written for a code-generating agent working in a modern frontend app that uses Vite, React 18, TypeScript 5.7, TanStack Router v1, TanStack Query v5, React Hook Form v7 + Zod v3, Tailwind CSS v3, Biome, Vitest, and Hey API OpenAPI codegen. It focuses on producing maintainable, idiomatic code with strong type-safety, predictable data flow, and enforceable quality gates.

## What good code means in this stack

Good code in React starts with **predictability**: rendering should be *pure*, meaning components compute JSX from inputs (props/state/context) and do not mutate pre-existing variables or cause side effects during render. React’s docs emphasize render purity explicitly because it makes behavior easier to understand and debug, and allows React to optimize effectively. citeturn7search0turn7search4

In this project, “good latest code” specifically means:

A component should **not use Effects as a default tool** for derived state. Effects are intended to synchronize with *external systems* (network, DOM, browser APIs, third-party widgets). If you’re just transforming data for rendering or reacting to a user event, React’s guidance is: you often don’t need an Effect, and removing unnecessary Effects makes code easier to follow and less error-prone. citeturn7search1turn7search24

Effects that *are* necessary must be written in a way that survives React 18 development behaviors. In Strict Mode, React performs an extra development-only setup+cleanup cycle for Effects (a stress test to validate cleanup correctness). Your cleanup must “mirror” setup and be safe to run more than once. citeturn7search3turn0search0turn0search32

React 18’s modern root API also changes performance characteristics: when you use `createRoot`, updates are automatically batched more broadly (not just inside React event handlers). That shifts performance pitfalls: it reduces accidental extra renders, but it also means you should rely less on ad-hoc micro-optimizations and more on correct state modeling. citeturn0search4

If you want a shorthand “agent mindset” for this repo:

Write code that is **locally understandable** (a file tells the truth without requiring hunting through unrelated files), **type-checked end-to-end**, and **fail-fast** with clear error boundaries and validation at the edges (URL state, API responses, and user input).

React is maintained by entity["company","Meta Platforms","technology company"], and the modern React docs are opinionated about purity and Effects because those constraints match how React’s rendering model works. citeturn7search0turn7search3turn7search4

## Project structure and TypeScript hygiene

### Prefer “feature slices” plus a small shared core

For a code agent, structure is a quality multiplier: it reduces the chance of emitting random grab-bag utilities and duplicated logic.

A practical layout that fits TanStack Router + Query + forms:

- `src/routes/…` (route files and route-adjacent UI)
- `src/features/<feature>/…` (domain-specific state, queries, forms, components)
- `src/shared/…` (design-system-ish primitives, generic utilities, fetch client wrapper, error helpers)
- `src/api/…` (generated Hey API client output + tiny adapters)

The critical rule for agents: **generated code stays generated** (isolated folder, never manually edited). Everything else is human-owned/agent-owned.

### Use TypeScript build mode intentionally

Your scripts already use `tsc -b`, which is TypeScript’s “build mode” used with project references. TypeScript explicitly positions project references as a way to split large programs into smaller pieces, improving build/editor performance and enforcing logical boundaries. citeturn11view2turn2search0

If your project is small, you may not need multiple referenced projects today—but since you already run `tsc -b`, the agent should:

- avoid writing code that depends on accidental type leakage across boundaries,
- keep shared types in a clear place (e.g., `src/shared/types` or generated API types),
- avoid cyclical imports (they show up as confusing runtime behavior in ESM projects and are painful for incremental builds).

### Favor explicit module intent with `verbatimModuleSyntax`

TypeScript’s `verbatimModuleSyntax` is designed to make emitted module code more predictable by requiring explicit `type` modifiers for type-only imports/exports; anything without `type` is treated as a value import/export and preserved accordingly. This eliminates ambiguity in “type stripping” and makes runtime module behavior more intentional. citeturn11view3turn2search1turn2search17

For an agent, this becomes a rule:

- If you import something only used as types, write `import type { … } from …`.
- If you export types, use `export type { … }`.

This keeps ESM output clean and prevents “it compiled but broke at runtime” class of issues described in the TypeScript docs around import elision. citeturn11view3turn2search17

### Treat Vite environment variables as public API

Vite exposes environment values on `import.meta.env`, but **only variables prefixed with `VITE_` are exposed to client code** (to prevent accidental leakage). Vite’s docs show this explicitly and note that build-time replacement is used so tree-shaking remains effective. citeturn10view0turn1search0

Agent rule: never invent secret environment variables in client code. If you see `VITE_*`, assume it is public and safe to ship; anything secret must stay server-side.

## Routing and URL state with TanStack Router

TanStack Router is built around **end-to-end inference**: routes and their params/search/context are designed so TypeScript can infer navigation and data requirements. The official overview highlights type-safe navigation, built-in route loaders with SWR-style caching, file-based route generation, and schema validation for path/search parameters. citeturn9search8turn0search10

### Make URL state typed, validated, and normalized

TanStack Router explicitly treats search params as first-class state and provides schema validation hooks (including Zod-based patterns) to make them safe and predictable. citeturn9search0turn9search4

A production approach is:

- Define a schema for search params.
- Validate search params at the route level.
- Normalize defaults and serialization (so links and programmatic navigation generate consistent URLs).

The Router docs show that search middlewares can transform search params during link generation and navigation (useful for defaulting/retaining parameters). citeturn9search4turn0search6

**Agent quality rule:** do not manually parse query strings with `URLSearchParams` in random components. Treat URL state as Router-managed state with validation.

### Prefer loaders as orchestration, not as “another fetch layer”

TanStack Router has a data loading system with route-level caching knobs. Defaults matter:

- default `staleTime` is 0 (data considered stale immediately),
- preload freshness defaults to 30 seconds,
- default `gcTime` is 30 minutes,
- staleReloadMode defaults to background (stale-while-revalidate). citeturn6search2turn6search4

This is *fantastic* if you rely on Router loaders as your caching layer. But you’re also using TanStack Query, whose core job is caching server state.

So: pick a primary caching layer per data family.

- If TanStack Query owns the cache: loaders should **prefetch into Query** (or ensure data exists) and leave “render-time fetching” to Query hooks.
- If Router owns the cache for a route: the component should mostly read `loaderData` and skip Query for that slice.

TanStack Router has an “External Data Loading” guide precisely because it expects Router to coordinate external async caches (like TanStack Query) in a way aligned with navigation and perceived freshness. citeturn6search30turn6search17

### Error boundaries are part of the routing design

TanStack Router supports route-level error boundaries and provides built-in error UI components such as `ErrorComponent`, with props and behavior documented in the API reference. citeturn9search2turn9search12

Agent rule: don’t swallow errors inside random components. If the error is route-critical, let it bubble to a route error boundary and render a route-appropriate fallback (or configure sensible defaults via router options). Router-level defaults for error components are documented (e.g., `defaultErrorComponent`). citeturn9search18

## Data fetching and caching with TanStack Query and generated API clients

TanStack Query v5 is the server-state backbone here: caching, refetching, mutations, invalidation, cancellation, and prefetching are first-class patterns. Its docs emphasize query keys as the basis of caching and refetching logic. citeturn8search0turn8search7

### Build query keys and query options as stable “public interfaces”

Query keys:

- must be arrays at the top level,
- should be serializable (e.g., JSON.stringify-able),
- must uniquely represent the data being cached. citeturn8search0turn8search23

A production pattern is to create key factories + options factories (and then the agent only composes them).

Example (key factory + options):

```ts
// src/features/lessons/queries.ts
import { queryOptions } from "@tanstack/react-query";

export const lessonsKeys = {
  all: ["lessons"] as const,
  list: (filters: { locale: string; page: number }) =>
    ["lessons", "list", filters] as const,
  byId: (id: string) => ["lessons", "byId", id] as const,
};

export function lessonsListOptions(filters: { locale: string; page: number }) {
  return queryOptions({
    queryKey: lessonsKeys.list(filters),
    queryFn: async ({ signal }) => {
      // pass AbortSignal through to fetch client when supported
      return fetchLessonsList({ ...filters, signal });
    },
    staleTime: 30_000,
  });
}
```

This matches TanStack Query’s guidance that keys drive caching, while functions return promises that resolve data or throw errors. citeturn8search0turn8search7turn8search3

### Respect (and tune) Query’s default refetch behavior

By default, Query aggressively keeps stale data fresh: stale queries are refetched in the background when new instances mount, the window refocuses, or the network reconnects. The docs recommend using `staleTime` to avoid excessive refetching and then fine-tuning refetch flags if needed. citeturn8search1turn8search20

Agent rule:

- If data is “mostly static” (feature flags, UI config, translations), set a long `staleTime` or disable `refetchOnWindowFocus`.
- If data is user-critical (session, assignments, timesensitive scoring), keep defaults (short staleTime) and rely on refetch behavior.

### Mutations must connect back to cache via invalidation (or direct updates)

TanStack Query’s docs highlight the standard pattern: when a mutation succeeds, invalidate the affected queries so the cache becomes stale and refetches. citeturn0search5turn0search1

For v5, also internalize that query callbacks like `onSuccess/onError` were removed from `useQuery` (but remain for mutations). That affects “side effect placement”: query side effects should be modeled differently (often via state machines, derived state, or Effects that react to query results), while mutation side effects stay mutation-owned. citeturn8search8turn0search9

### Cancellation is not optional: wire AbortSignal through

TanStack Query provides an `AbortSignal` to query functions; when a query becomes out-of-date/inactive, the signal is aborted, enabling automatic cancellation without giving up async/await. citeturn8search3

Agent rule: if the underlying fetch technology supports it, accept `{ signal }` and pass it through. This matters a lot when search params drive fast-changing queries (search-as-you-type, pagination, filters).

### Use router integration prefetching to avoid waterfalls

TanStack Query’s prefetching guide explicitly calls out routing use cases and multiple prefetch patterns, including router integration, and notes how prefetch respects staleTime and how `ensureQueryData` can be used when you want “use cached data if present, fetch otherwise.” citeturn13view1turn6search0turn6search23

A practical TanStack Router + Query loader pattern is:

- In loader: `await queryClient.ensureQueryData(…options…)`
- In component: read via `useQuery` / `useSuspenseQuery` using the same options factory

This aligns with Router’s design goal of coordinating external caches. citeturn6search30turn6search13turn6search17

### Generate API clients with Hey API and keep a thin wrapper

Hey API’s OpenAPI generator (`@hey-api/openapi-ts`) is designed to generate TypeScript SDKs and types from OpenAPI specs, with plugin-based customization and multiple HTTP client targets (including Fetch). citeturn10view1turn3search15

Two operational facts that matter for an automated agent:

- The docs state the generator runs in a Node.js 20+ environment. citeturn10view1
- It is “in initial development” and recommends pinning an exact version so upgrades are deliberate. citeturn10view1

That guidance conflicts with a caret range (`^0.66.0`) if you want **reproducible generation**. If the goal is “not slop,” reproducibility matters: generated code should not silently change between runs.

For the Fetch client: the `@hey-api/client-fetch` package is described as a type-safe Fetch API client intended to integrate with the generator, offering typed response data and errors, access to original request/response, and customization hooks. citeturn3search11turn3search38turn3search26

**Recommended layering:**

- `src/api/generated/…` (output of openapi-ts; never edited)
- `src/api/http.ts` (configure base URL, auth behavior, error mapping)
- `src/features/*/api.ts` (domain functions: `getLesson`, `updateProgress`, …)
- `src/features/*/queries.ts` (query key & options factories)

This avoids a common agent failure mode: calling generated endpoints directly from UI components everywhere.

Hey API is used by companies like entity["company","Vercel","web hosting company"] and entity["company","PayPal","payments company"], and features a testimonial from entity["people","Guillermo Rauch","vercel ceo"] in its docs, which is a signal that it’s widely used—but the versioning note is the more operationally important detail for automation. citeturn10view1

## Forms and validation with React Hook Form and Zod

This stack uses Zod for runtime validation and React Hook Form (RHF) for form state + submission, alongside `@hookform/resolvers` for schema integration.

### Zod should be the single source of truth for form data shape

Zod is explicitly “TypeScript-first,” allowing you to define schemas and parse unknown data into validated, type-safe results. citeturn3search0turn3search12

Agent rule: define a schema, then derive the TS type from it (don’t hand-write an interface that can drift).

Zod supports safe parsing; Zod’s docs and examples emphasize `.parse` as “validate or throw,” while `.safeParse` returns a success/error result object, which is useful for user input flows and error formatting. citeturn3search0turn3search4turn3search16

### Use resolvers for schema-based RHF validation

`@hookform/resolvers` exists specifically to connect RHF to external validation libraries (including Zod). citeturn3search2turn3search14

Your dominant production pattern should be:

- schema defines constraints
- RHF is wired via `resolver: zodResolver(schema)`
- UI reads `formState.errors` and shows messages consistently

This yields consistent runtime behavior and reduces agent hallucinations about validation logic.

### Don’t hide errors in submit handlers

RHF’s docs for `handleSubmit` note that it will not swallow errors thrown inside your `onSubmit` callback, and recommends catching errors inside async submit handlers. citeturn3search1

Agent implication: if the submit handler calls a mutation and can throw (network error, Zod parse error, unexpected API shape), it should:

- catch and map the error to UI state,
- or explicitly rethrow to a route-level boundary if the form cannot recover.

### Be conservative about “latest” upgrades across the RHF/Zod boundary

You are on Zod v3. There have been ecosystem frictions reported when upgrading to Zod v4 in combination with RHF resolvers (type-system differences impacting integration). citeturn3search29

If “latest code” is the goal, the safe approach is “upgrade deliberately with tests,” not “auto-bump.”

## UI composition with Tailwind, icons, and Motion

### Tailwind CSS: make content scanning explicit and stable

Tailwind generates CSS by scanning your source files for class names; its v3 docs are explicit that you must configure content paths so Tailwind sees every file that contains Tailwind classes. citeturn4search3turn4search7

Agent rule: when adding new directories of JSX/TSX templates (e.g., `src/features/...`), ensure those paths are covered by Tailwind’s `content` globs, otherwise styles will “randomly” disappear in production builds.

Also note: Tailwind has multiple installation modes and evolving integration guidance, including Vite-based setups, but your dependency versions indicate Tailwind v3, so rely on v3 guides (not v4-only plugin patterns). citeturn1search5turn4search3

### Lucide: import icons directly and rely on tree-shaking

Lucide’s React docs state that icons are standalone React components, customizable via props, and tree-shakable—only imported icons end up in the final bundle. citeturn13view3turn4search5

It also documents a default size (24×24) and the `size` prop for adjustment. citeturn4search17

Agent rule: never create wrapper modules that re-export “all icons,” because that defeats tree-shaking and inflates bundles.

### Motion and animation: prefer layout animations + reduced motion compliance

Motion (formerly Framer Motion) supports layout animations via a `layout` prop and shared element transitions via `layoutId`. citeturn4search0turn4search8

For accessibility, Motion provides:

- `useReducedMotion`, which returns `true` if the device has Reduced Motion enabled. citeturn14search0
- `MotionConfig reducedMotion="user"`, which sets a site-wide policy; docs note that when reduced motion is on, transform and layout animations are disabled while opacity/backgroundColor can persist. citeturn14search1turn14search2

This aligns with the broader web platform concept of the `prefers-reduced-motion` media feature for detecting user preference to minimize non-essential motion. citeturn14search21

Agent rule: any non-trivial animation should either:
- be wrapped in a global reduced motion policy (recommended), or
- explicitly consult `useReducedMotion` for large transform animations.

If your repo stays on the `framer-motion` package, keep imports consistent. Motion’s upgrade materials describe a migration path that swaps imports from `framer-motion` to `motion/react` if you adopt the renamed package. citeturn14search24

## Quality gates and “anti-slop” automation with Biome and Vitest

### Biome is the authoritative formatter and linter

Biome provides a unified CLI; the docs define:

- `biome check`: runs formatter, linter, and import sorting
- `biome ci`: CI-optimized equivalent that does not modify files
- `biome format` and `biome lint` as narrower commands. citeturn10view3turn5search0turn5search9

Biome’s formatter is explicitly opinionated and intentionally resists excessive configuration (similar philosophy to Prettier): fewer knobs, fewer team debates, more consistency. citeturn5search1turn5search4

Agent rule: don’t fight formatting. Emit idiomatic code and let Biome normalize it.

**Important detail for your stack:** Biome’s CSS formatter is disabled by default (`css.formatter.enabled` default is false), while CSS linting is enabled by default. In Tailwind-heavy projects, this can surprise teams who expect `biome check` to format CSS files. citeturn5search7

If you want formatted CSS, it must be enabled explicitly in Biome config.

Also worth knowing operationally: there were reports of Biome 2.1.1 “hanging” in some environments, and Biome provides a slowness investigation guide for diagnosing slow scans/module graph work. Since your project pins 2.1.1, this is relevant if your agent starts timing out in CI. citeturn0search23turn0search35turn0search15

Biome also documents Git hook setups to run checks on commit/push, which is a strong defense against accidental regressions from automated code changes. citeturn0search7

### Vitest is the test runner; know its run modes and config model

Vitest’s CLI docs define:

- `vitest run`: single run (non-watch)
- `vitest watch` / `vitest dev`: watch mode
- calling `vitest` defaults to watch in dev and falls back to run in CI/non-interactive terminals. citeturn11view1turn5search2

Vitest also documents config precedence and how it reads Vite config by default, plus the TypeScript “triple-slash” reference needed to use `test:` configuration in a Vite config when importing `defineConfig` from Vite. citeturn13view0turn1search18

Agent rule: when adding tests, also ensure test configuration is coherent (jsdom, setup files, aliases). Avoid “it works locally but not in CI” by relying on documented run vs watch behavior.

TanStack Query provides explicit testing guidance (e.g., considerations around cache garbage collection and testing network calls), which matters if your tests instantiate Query clients or rely on query caching behavior. citeturn5search11

### A definition of done that a code agent can follow

A code agent produces “AI slop” when it ships code that *looks plausible* but is not integrated into the project’s enforcement mechanisms. The fix is to define non-negotiable gates that match your scripts and toolchain behavior.

For this repo, the minimal non-negotiable standard should be equivalent to running:

- `biome check .` (format, lint, import sorting) citeturn10view3turn5search0  
- `tsc -b --noEmit` (build-mode typecheck aligned with project references) citeturn11view2turn2search0  
- `vitest run` (single-run tests) citeturn11view1turn5search2  

If any of these fail, the output isn’t “done,” regardless of how clean the diff looks.

### A copy-pastable code-agent directive for this stack

Use the block below as a “system prompt” / instruction snippet for your agent (adapt naming to your repo). It is deliberately specific to prevent generic filler output.

```text
You are writing code for a Vite + React 18 + TypeScript 5.7 app that uses:
- TanStack Router v1 for routing and URL state (search params validated via schemas)
- TanStack Query v5 for server-state caching and mutations
- React Hook Form v7 + @hookform/resolvers + Zod v3 for forms and validation
- Tailwind CSS v3 for styling
- Biome for formatting/linting/import sorting
- Vitest for tests
- Hey API OpenAPI codegen (+ client-fetch) for typed API clients

Non-negotiable output rules:
- No TODOs, placeholders, fake endpoints, or “assume this exists” helpers unless you also implement them.
- Do not parse URL query strings manually; use TanStack Router search param APIs + validation.
- All data fetching must go through TanStack Query (query key factory + queryOptions factory) unless the route loader cache is explicitly the chosen cache.
- Query keys must be array-based, stable, and serializable.
- Mutations must update or invalidate relevant queries.
- Pass AbortSignal through query functions when supported.
- Keep React render pure; avoid unnecessary useEffect. Effects only for external synchronization.
- Respect reduced-motion preferences for non-trivial animations.
- Generated API code stays in the generated folder; do not edit generated files.