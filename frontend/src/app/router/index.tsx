import { createRouter, RouterProvider } from "@tanstack/react-router";

import { queryClient } from "../../shared/lib/query-client";
import { accountRoute } from "./account-routes";
import { indexRoute, loginRoute, registerRoute } from "./auth-routes";
import { kanaLessonRoute, kanaRoute, kanjiRoute, lessonRoute, pathRoute } from "./learning-routes";
import { rootRoute } from "./root-route";

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  pathRoute,
  lessonRoute,
  kanaRoute,
  kanaLessonRoute,
  kanjiRoute,
  accountRoute,
]);

const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  context: { queryClient },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function AppRouter() {
  return <RouterProvider router={router} context={{ queryClient }} />;
}
