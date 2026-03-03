import { useQuery } from "@tanstack/react-query";

import { authHeaders, currentCourseApiV1CourseCurrentGet, meApiV1AuthMeGet } from "../api";
import type { CurrentCourseResponse, MeResponse } from "../api/generated/types.gen";
import { getToken } from "./token-store";

export const sessionKeys = {
  me: ["session", "me"] as const,
  currentCourse: ["session", "current-course"] as const,
};

export function isAuthenticated(): boolean {
  return getToken().length > 0;
}

function requireData<T>(data: T | undefined): T {
  if (data === undefined) {
    throw new Error("API response was empty.");
  }
  return data;
}

export function useMeQuery(enabled = isAuthenticated()) {
  return useQuery({
    queryKey: sessionKeys.me,
    queryFn: async () => {
      const result = await meApiV1AuthMeGet({ headers: authHeaders(getToken()) });
      return requireData<MeResponse>(result.data as MeResponse | undefined);
    },
    enabled,
    staleTime: 60_000,
  });
}

export function useCurrentCourseQuery(enabled = isAuthenticated()) {
  return useQuery({
    queryKey: sessionKeys.currentCourse,
    queryFn: async () => {
      const result = await currentCourseApiV1CourseCurrentGet({
        headers: authHeaders(getToken()),
      });
      return requireData<CurrentCourseResponse>(result.data as CurrentCourseResponse | undefined);
    },
    enabled,
    staleTime: 60_000,
  });
}
