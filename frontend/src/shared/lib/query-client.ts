import { QueryClient } from "@tanstack/react-query";

/** Single app-wide client (shared by `RouterProvider` loaders and `QueryClientProvider`). */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});
