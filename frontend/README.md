# Speedrulingo Frontend

This folder contains the React web app for Speedrulingo.

## Stack

- React
- TypeScript
- Vite
- TanStack Router
- TanStack Query
- Biome
- Vitest

## Main Areas

- `src/pages/` route-level pages
- `src/features/` feature-specific queries and mutations
- `src/shared/api/` generated API client and shared API utilities
- `src/shared/auth/` auth/session helpers
- `src/shared/styles/` global styles

## Development

From this directory:

```bash
npm install
npm run dev
```

Useful commands:

```bash
npm run verify
npm run generate:api
```

## Notes

- The lesson flow is in better shape than the rest of the UI.
- The frontend is usable, but still visually unfinished in several areas.
- The frontend is wired to a generated API client rather than handwritten fetch wrappers.
