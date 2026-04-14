import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  authedRequestHeaders,
  requireResponseData,
  unitDetailApiV1UnitsUnitIdGet,
} from "../../shared/api";
import type { UnitDetail } from "../../shared/api/generated/types.gen";

export const unitKeys = {
  all: ["units"] as const,
  detail: (unitId: string) => ["units", unitId] as const,
};

function unitDetailQueryOptions(unitId: string | null) {
  return queryOptions({
    queryKey: unitKeys.detail(unitId ?? ""),
    queryFn: async ({ signal }) => {
      if (!unitId) {
        throw new Error("Missing unit id.");
      }
      const result = await unitDetailApiV1UnitsUnitIdGet({
        headers: authedRequestHeaders(),
        path: { unit_id: unitId },
        signal,
      });
      return requireResponseData(result as { data: UnitDetail | undefined; response: Response });
    },
    enabled: Boolean(unitId),
    staleTime: 30_000,
  });
}

export function useUnitDetailQuery(unitId: string | null) {
  return useQuery(unitDetailQueryOptions(unitId));
}
