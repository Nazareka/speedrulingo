import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  authHeaders,
  loginApiV1AuthLoginPost,
  registerApiV1AuthRegisterPost,
} from "../../shared/api";
import type { TokenResponse } from "../../shared/api/generated/types.gen";
import { sessionKeys } from "../../shared/auth/session";
import { getToken, setToken } from "../../shared/auth/token-store";

function requireData<T>(data: T | undefined): T {
  if (data === undefined) {
    throw new Error("API response was empty.");
  }
  return data;
}

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { email: string; password: string }) => {
      const result = await loginApiV1AuthLoginPost({ body: payload });
      return requireData<TokenResponse>(result.data as TokenResponse | undefined);
    },
    onSuccess: async (data) => {
      setToken(data.access_token);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: sessionKeys.me }),
        queryClient.invalidateQueries({ queryKey: sessionKeys.currentCourse }),
      ]);
    },
  });
}

export function useRegisterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { email: string; password: string }) => {
      const result = await registerApiV1AuthRegisterPost({ body: payload });
      return requireData<TokenResponse>(result.data as TokenResponse | undefined);
    },
    onSuccess: async (data) => {
      setToken(data.access_token);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: sessionKeys.me }),
        queryClient.invalidateQueries({ queryKey: sessionKeys.currentCourse }),
      ]);
    },
  });
}

export function buildAuthedHeaders(): Record<string, string> | undefined {
  return authHeaders(getToken());
}
