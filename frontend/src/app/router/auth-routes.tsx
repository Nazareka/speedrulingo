import { createRoute, redirect } from "@tanstack/react-router";

import { LoginPage } from "../../pages/login-page";
import { RegisterPage } from "../../pages/register-page";
import { hasAuthToken } from "../../shared/auth/token-store";
import { authRouteSearchSchema } from "../../shared/lib/auth-route-search";
import { rootRoute } from "./root-route";

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: hasAuthToken() ? "/path" : "/login" });
  },
});

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
  validateSearch: (raw) => authRouteSearchSchema.parse(raw),
});

export const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/register",
  component: RegisterPage,
  validateSearch: (raw) => authRouteSearchSchema.parse(raw),
});
