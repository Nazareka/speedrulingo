import type { QueryClient } from "@tanstack/react-query";
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MotionConfig } from "framer-motion";
import type { ReactElement, ReactNode } from "react";

import { createTestQueryClient } from "./create-test-query-client";

type ProviderOptions = {
  queryClient?: QueryClient;
};

/**
 * Matches production shell: React Query + MotionConfig.
 * Tests use `reducedMotion="never"` to avoid animation timing flakes.
 *
 * For router integration tests, use `RouterProvider` from `@tanstack/react-router` with
 * `context: { queryClient }` where `queryClient` is from `createTestQueryClient()` (see `../app/router`).
 */
function TestProviders({ children, queryClient }: ProviderOptions & { children: ReactNode }) {
  const client = queryClient ?? createTestQueryClient();
  return (
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="never">{children}</MotionConfig>
    </QueryClientProvider>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  options?: ProviderOptions & Omit<NonNullable<Parameters<typeof render>[1]>, "wrapper">,
) {
  const { queryClient: qcFromOpts, ...renderOptions } = options ?? {};
  const queryClient = qcFromOpts ?? createTestQueryClient();
  return {
    queryClient,
    ...render(ui, {
      ...renderOptions,
      wrapper: ({ children }) => (
        <TestProviders queryClient={queryClient}>{children}</TestProviders>
      ),
    }),
  };
}
