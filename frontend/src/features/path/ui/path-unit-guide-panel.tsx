import type { UseQueryResult } from "@tanstack/react-query";
import { UnitGuideCard } from "../../../entities/unit/unit-guide-card";
import type { UnitDetail } from "../../../shared/api/generated/types.gen";

type UnitDetailQuery = UseQueryResult<UnitDetail>;

const panelMuted = "text-[var(--lesson-text-muted)] text-sm";

/**
 * Side panel for the selected unit’s guide — presentation only; data comes from parent queries.
 */
export function PathUnitGuidePanel({
  guideUnitId,
  guideUnitQuery,
}: {
  guideUnitId: string | null;
  guideUnitQuery: UnitDetailQuery;
}) {
  if (!guideUnitId) {
    return <p className={panelMuted}>Select a unit in the carousel to see its guide.</p>;
  }

  const q = guideUnitQuery;

  if (q.isError) {
    return (
      <p className={panelMuted}>
        The guide could not be loaded. Try again in a moment or pick another unit.
      </p>
    );
  }

  if (q.isPending && !q.data) {
    return (
      <div className="h-80 animate-pulse rounded-[1.75rem] bg-[var(--lesson-surface-muted)]" />
    );
  }

  if (q.data) {
    const refetchWhileShowing = q.isFetching && !q.isPending;
    return (
      <div className="relative">
        {refetchWhileShowing ? (
          <span aria-live="polite" className="sr-only">
            Updating guide…
          </span>
        ) : null}
        <div className={refetchWhileShowing ? "opacity-95 transition-opacity" : undefined}>
          <UnitGuideCard unit={q.data} />
        </div>
      </div>
    );
  }

  return <p className={panelMuted}>No guide content is available for this unit.</p>;
}
