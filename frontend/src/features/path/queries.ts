import { queryOptions, useQuery } from "@tanstack/react-query";

import { authedRequestHeaders, pathApiV1PathGet, requireResponseData } from "../../shared/api";
import type { PathResponse } from "../../shared/api/generated/types.gen";

export const pathKeys = {
  all: ["path"] as const,
};

export function pathQueryOptions() {
  return queryOptions({
    queryKey: pathKeys.all,
    queryFn: async ({ signal }) => {
      const result = await pathApiV1PathGet({ headers: authedRequestHeaders(), signal });
      return requireResponseData(result.data as PathResponse | undefined);
    },
    staleTime: 30_000,
  });
}

export function usePathQuery() {
  return useQuery(pathQueryOptions());
}
