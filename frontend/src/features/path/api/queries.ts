import { queryOptions, useQuery } from "@tanstack/react-query";

import { pathKeys } from "../../../entities/path/query-keys";
import { authedRequestHeaders, pathApiV1PathGet, requireResponseData } from "../../../shared/api";
import type { PathResponse } from "../../../shared/api/generated/types.gen";

export { pathKeys } from "../../../entities/path/query-keys";

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
