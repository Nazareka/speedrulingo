import { useQuery } from "@tanstack/react-query";

import { pathApiV1PathGet } from "../../shared/api";
import type { PathResponse } from "../../shared/api/generated/types.gen";
import { buildAuthedHeaders } from "../auth/mutations";

export const pathKeys = {
  all: ["path"] as const,
};

export function usePathQuery() {
  return useQuery({
    queryKey: pathKeys.all,
    queryFn: async () => {
      const result = await pathApiV1PathGet({ headers: buildAuthedHeaders() });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as PathResponse;
    },
    staleTime: 30_000,
  });
}
