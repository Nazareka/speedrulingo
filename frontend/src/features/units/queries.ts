import { useQuery } from "@tanstack/react-query";

import { unitDetailApiV1UnitsUnitIdGet, unitsApiV1UnitsGet } from "../../shared/api";
import type { UnitDetail, UnitSummary } from "../../shared/api/generated/types.gen";
import { buildAuthedHeaders } from "../auth/mutations";

export const unitKeys = {
  all: ["units"] as const,
  detail: (unitId: string) => ["units", unitId] as const,
};

export function useUnitsQuery() {
  return useQuery({
    queryKey: unitKeys.all,
    queryFn: async () => {
      const result = await unitsApiV1UnitsGet({ headers: buildAuthedHeaders() });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as Array<UnitSummary>;
    },
    staleTime: 30_000,
  });
}

export function useUnitDetailQuery(unitId: string | null) {
  return useQuery({
    queryKey: unitKeys.detail(unitId ?? ""),
    queryFn: async () => {
      if (!unitId) {
        throw new Error("Missing unit id.");
      }
      const result = await unitDetailApiV1UnitsUnitIdGet({
        headers: buildAuthedHeaders(),
        path: { unit_id: unitId },
      });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as UnitDetail;
    },
    enabled: Boolean(unitId),
    staleTime: 30_000,
  });
}
