import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  authHeaders,
  currentCourseApiV1CourseCurrentGet,
  meApiV1AuthMeGet,
  requireResponseData,
} from "../api";
import type { CurrentCourseResponse, MeResponse } from "../api/generated/types.gen";
import { getToken } from "./token-store";

export const sessionKeys = {
  me: ["session", "me"] as const,
  currentCourse: ["session", "current-course"] as const,
};

function isAuthenticated(): boolean {
  return getToken().length > 0;
}

export function meQueryOptions(enabled: boolean) {
  return queryOptions({
    queryKey: sessionKeys.me,
    queryFn: async ({ signal }) => {
      const result = await meApiV1AuthMeGet({ headers: authHeaders(getToken()), signal });
      return requireResponseData(result.data as MeResponse | undefined);
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
      return requireResponseData(result.data as CurrentCourseResponse | undefined);
    },
    staleTime: 60_000,
    enabled,
  });
}

export function useMeQuery(enabled = isAuthenticated()) {
  return useQuery(meQueryOptions(enabled));
}

export function useCurrentCourseQuery(enabled = isAuthenticated()) {
  return useQuery(currentCourseQueryOptions(enabled));
}
