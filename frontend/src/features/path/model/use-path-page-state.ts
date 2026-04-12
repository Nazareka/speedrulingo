import { useCallback, useMemo, useState } from "react";
import {
  allUnitsFlatFromPath,
  deriveInitialSelection,
  normalizePathSelection,
  type PathSelection,
  pathSelectionForSectionChange,
  pathSelectionForUnitPick,
  pathSlidesForSection,
} from "../../../entities/path/model";
import { useUnitDetailQuery } from "../../../entities/unit/queries";
import { useCurrentCourseQuery } from "../../../shared/auth/session";
import { usePathQuery } from "../api/queries";

/** Binds manual selection to server progress so it is ignored after progress/course changes (no effect-based clear). */
type ManualSelectionState = {
  selection: PathSelection;
  progressKey: string;
};

export function usePathPageState() {
  const pathQuery = usePathQuery();
  const currentCourseQuery = useCurrentCourseQuery();
  const activeUnitId = pathQuery.data?.current_unit_id ?? null;

  const derivedSelection = useMemo(
    () => (pathQuery.data ? deriveInitialSelection(pathQuery.data, activeUnitId) : null),
    [pathQuery.data, activeUnitId],
  );

  const [manualSelection, setManualSelection] = useState<ManualSelectionState | null>(null);

  const courseVersionId = currentCourseQuery.data?.course_version_id;
  const progressKey = useMemo(
    () => `${courseVersionId ?? ""}|${activeUnitId ?? ""}`,
    [courseVersionId, activeUnitId],
  );

  const effectiveSelection = useMemo(() => {
    if (!pathQuery.data) return null;
    const manual =
      manualSelection !== null && manualSelection.progressKey === progressKey
        ? manualSelection.selection
        : null;
    const base = manual ?? derivedSelection;
    if (!base) return null;
    return normalizePathSelection(pathQuery.data, base);
  }, [pathQuery.data, manualSelection, derivedSelection, progressKey]);

  const pathSlides = useMemo(
    () =>
      pathQuery.data
        ? pathSlidesForSection(pathQuery.data, effectiveSelection?.selectedSectionId ?? null)
        : [],
    [pathQuery.data, effectiveSelection?.selectedSectionId],
  );

  const allUnitsFlat = useMemo(
    () => (pathQuery.data ? allUnitsFlatFromPath(pathQuery.data) : []),
    [pathQuery.data],
  );

  const guideUnitId = effectiveSelection?.selectedUnitId ?? null;
  const guideUnitQuery = useUnitDetailQuery(guideUnitId);

  const handleSelectSection = useCallback(
    (sectionId: string) => {
      if (!pathQuery.data) return;
      const next = pathSelectionForSectionChange(pathQuery.data, sectionId);
      if (next) setManualSelection({ selection: next, progressKey });
    },
    [pathQuery.data, progressKey],
  );

  const handlePickUnitFromAll = useCallback(
    (unitId: string) => {
      if (!pathQuery.data) return;
      const next = pathSelectionForUnitPick(pathQuery.data, unitId);
      if (next) setManualSelection({ selection: next, progressKey });
    },
    [pathQuery.data, progressKey],
  );

  const handleCarouselUnitChange = useCallback(
    (unitId: string) => {
      const data = pathQuery.data;
      if (!data) return;
      setManualSelection((prev) => {
        const base =
          (prev !== null && prev.progressKey === progressKey ? prev.selection : null) ??
          deriveInitialSelection(data, activeUnitId);
        const selection = normalizePathSelection(data, { ...base, selectedUnitId: unitId });
        return { selection, progressKey };
      });
    },
    [pathQuery.data, activeUnitId, progressKey],
  );

  return {
    pathQuery,
    currentCourseQuery,
    activeUnitId,
    effectiveSelection,
    pathSlides,
    allUnitsFlat,
    guideUnitId,
    guideUnitQuery,
    handleSelectSection,
    handlePickUnitFromAll,
    handleCarouselUnitChange,
  };
}
