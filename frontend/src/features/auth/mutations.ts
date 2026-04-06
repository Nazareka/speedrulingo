import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  loginApiV1AuthLoginPost,
  registerApiV1AuthRegisterPost,
  requireResponseData,
} from "../../shared/api";
import type { TokenResponse } from "../../shared/api/generated/types.gen";
import { sessionKeys } from "../../shared/auth/session";
import { setToken } from "../../shared/auth/token-store";

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { email: string; password: string }) => {
      const result = await loginApiV1AuthLoginPost({ body: payload });
      return requireResponseData(result.data as TokenResponse | undefined);
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
      return requireResponseData(result.data as TokenResponse | undefined);
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
