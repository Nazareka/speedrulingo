import { createRoute, redirect } from "@tanstack/react-router";

import { AccountPage } from "../../pages/account-page";
import { currentCourseQueryOptions, meQueryOptions } from "../../shared/auth/session";
import { hasAuthToken } from "../../shared/auth/token-store";
import { rootRoute } from "./root-route";

export const accountRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/account",
  component: AccountPage,
  beforeLoad: () => {
    if (!hasAuthToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(meQueryOptions(true)),
      context.queryClient.ensureQueryData(currentCourseQueryOptions(true)),
    ]),
});
