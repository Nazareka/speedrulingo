import { QueryClient } from "@tanstack/react-query";

import { isSessionExpiredError } from "../api/client/http";

/** Single app-wide client (shared by `RouterProvider` loaders and `QueryClientProvider`). */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (isSessionExpiredError(error)) {
          return false;
        }
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});
