import { QueryClient } from "@tanstack/react-query";

/** Isolated client for tests (no shared cache with the app singleton). */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}
