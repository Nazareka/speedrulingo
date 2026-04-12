import { defineConfig } from "vitest/config";

/**
 * Merges with vite.config.ts (Vitest uses the same Vite pipeline).
 * Keep `globals` aligned with tsconfig.app.json `types: ["vitest/globals"]`.
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    clearMocks: true,
    restoreMocks: true,
    passWithNoTests: true,
    /**
     * Coverage runs only with `vitest run --coverage` (see `package.json` `coverage` / `verify:ci`).
     * Aggregate thresholds match the current tested surface; stricter `session-*.ts` applies to
     * files that remain in the report (see `exclude` — `shared/lesson/session-model.ts` matches).
     */
    coverage: {
      provider: "v8",
      reportsDirectory: "./node_modules/.cache/vitest-coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/shared/api/generated/**",
        "src/test/**",
        "**/*.d.ts",
        // Not covered by unit tests yet; keep them out so `session-*.ts` glob matches model-only.
        "src/features/lesson/session-selectors.ts",
        "src/features/lesson/session-transitions.ts",
        "src/features/lesson/session-state.ts",
        "src/shared/lesson/session-types.ts",
        "src/features/lesson/use-lesson-session.ts",
      ],
      thresholds: {
        perFile: false,
        lines: 6,
        statements: 6,
        branches: 55,
        functions: 38,
        "src/features/lesson/session-*.ts": {
          lines: 88,
          functions: 85,
          branches: 85,
          statements: 88,
        },
        "src/shared/lesson/session-*.ts": {
          lines: 88,
          functions: 85,
          branches: 85,
          statements: 88,
        },
      },
    },
  },
});
