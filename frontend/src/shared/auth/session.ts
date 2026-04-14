/**
 * Authenticated “who am I / which course” reads used by multiple features and widgets.
 *
 * **Keep this module small.** Allowed here:
 * – `sessionKeys` wiring (see `session-keys.ts`)
 * – `queryOptions` builders for `/me` and current course
 * – Thin `useQuery` wrappers tied to those options
 *
 * **Do not add:** logout flows, permission matrices, profile business rules, or redirect
 * policy — those belong in `features/` (or route code) so this file stays cache/query only.
 * Token persistence stays in `token-store.ts`.
 */
import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  authHeaders,
  currentCourseApiV1CourseCurrentGet,
  meApiV1AuthMeGet,
  requireResponseData,
} from "../api";
import type { CurrentCourseResponse, MeResponse } from "../api/generated/types.gen";
import { sessionKeys } from "./session-keys";
import { getToken, hasAuthToken } from "./token-store";

export function meQueryOptions(enabled: boolean) {
  return queryOptions({
    queryKey: sessionKeys.me,
    queryFn: async ({ signal }) => {
      const result = await meApiV1AuthMeGet({ headers: authHeaders(getToken()), signal });
      return requireResponseData(result as { data: MeResponse | undefined; response: Response });
    },
    staleTime: 60_000,
    enabled,
  });
}

export function currentCourseQueryOptions(enabled: boolean) {
  return queryOptions({
    queryKey: sessionKeys.currentCourse,
    queryFn: async ({ signal }) => {
      const result = await currentCourseApiV1CourseCurrentGet({
        headers: authHeaders(getToken()),
        signal,
      });
      return requireResponseData(
        result as { data: CurrentCourseResponse | undefined; response: Response },
      );
    },
    staleTime: 60_000,
    enabled,
  });
}

export function useMeQuery(enabled = hasAuthToken()) {
  return useQuery(meQueryOptions(enabled));
}

export function useCurrentCourseQuery(enabled = hasAuthToken()) {
  return useQuery(currentCourseQueryOptions(enabled));
}
