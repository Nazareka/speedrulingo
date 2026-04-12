import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext } from "@tanstack/react-router";

import { AppFrame } from "../../widgets/app-shell/app-frame";
import { RouteErrorFallback } from "../route-error-fallback";

export const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: AppFrame,
  errorComponent: RouteErrorFallback,
});
