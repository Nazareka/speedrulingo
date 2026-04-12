import type { PathResponse, SectionUnits, UnitSummary } from "../../shared/api/generated/types.gen";

/** One unit shown in the path carousel / all-units list. */
export type PathUnitSlide = { sectionTitle: string; unit: UnitSummary };

/** User intent for the path page: which section and unit are selected. */
export type PathSelection = {
  selectedSectionId: string | null;
  selectedUnitId: string | null;
};

function sortedUnits(section: SectionUnits) {
  return [...section.units].sort((a, b) => a.unit_order_index - b.unit_order_index);
}

/** First unit in section order (for “pick section → show first unit”). */
function firstUnitIdInSection(section: SectionUnits): string | null {
  const ordered = sortedUnits(section);
  return ordered[0]?.id ?? null;
}

/**
 * Default selection from path data: follow API active unit, else first unit of first section.
 */
export function deriveInitialSelection(
  data: PathResponse,
  activeUnitId: string | null,
): PathSelection {
  if (activeUnitId) {
    for (const section of data.sections) {
      const unit = section.units.find((u) => u.id === activeUnitId);
      if (unit) {
        return { selectedSectionId: section.id, selectedUnitId: unit.id };
      }
    }
  }

  const firstSection = data.sections[0];
  const firstUnit = firstSection ? sortedUnits(firstSection)[0] : undefined;

  return {
    selectedSectionId: firstSection?.id ?? null,
    selectedUnitId: firstUnit?.id ?? null,
  };
}

/**
 * If the selected unit is missing from the selected section (stale id), fall back to first unit.
 */
export function normalizePathSelection(data: PathResponse, base: PathSelection): PathSelection {
  if (!base.selectedSectionId) {
    if (base.selectedUnitId) {
      const rescued = pathSelectionForUnitPick(data, base.selectedUnitId);
      if (rescued) return rescued;
    }
    return deriveInitialSelection(data, null);
  }
  const section = data.sections.find((s) => s.id === base.selectedSectionId);
  if (!section) {
    return deriveInitialSelection(data, null);
  }
  const ordered = sortedUnits(section);
  if (ordered.length === 0) {
    return { selectedSectionId: base.selectedSectionId, selectedUnitId: null };
  }
  if (base.selectedUnitId && ordered.some((u) => u.id === base.selectedUnitId)) {
    return base;
  }
  const first = ordered[0];
  if (!first) {
    return { selectedSectionId: base.selectedSectionId, selectedUnitId: null };
  }
  return { selectedSectionId: base.selectedSectionId, selectedUnitId: first.id };
}

/** Ordered units in a section as carousel slides. */
export function pathSlidesForSection(
  data: PathResponse,
  sectionId: string | null,
): PathUnitSlide[] {
  if (!sectionId) return [];
  const section = data.sections.find((s) => s.id === sectionId);
  if (!section) return [];
  return sortedUnits(section).map((unit) => ({ sectionTitle: section.title, unit }));
}

/** Every unit in course order (section order, then unit order). */
export function allUnitsFlatFromPath(data: PathResponse): PathUnitSlide[] {
  return data.sections.flatMap((section) =>
    sortedUnits(section).map((unit) => ({ sectionTitle: section.title, unit })),
  );
}

/** True when every section has at least one unit and every unit is completed. */
export function isCourseFullyCompleted(data: PathResponse): boolean {
  return (
    data.sections.length > 0 &&
    data.sections.every((s) => s.units.length > 0 && s.units.every((u) => u.is_completed))
  );
}

export function findSectionById(data: PathResponse, sectionId: string | null): SectionUnits | null {
  if (sectionId == null) return null;
  return data.sections.find((s) => s.id === sectionId) ?? null;
}

/**
 * Selection after user picks a section (first unit in that section, normalized).
 */
export function pathSelectionForSectionChange(
  data: PathResponse,
  sectionId: string,
): PathSelection | null {
  const section = data.sections.find((s) => s.id === sectionId);
  if (!section) return null;
  return normalizePathSelection(data, {
    selectedSectionId: sectionId,
    selectedUnitId: firstUnitIdInSection(section),
  });
}

/**
 * Selection after user picks a unit from the all-units list (section + unit, normalized).
 */
export function pathSelectionForUnitPick(data: PathResponse, unitId: string): PathSelection | null {
  for (const section of data.sections) {
    const unit = section.units.find((u) => u.id === unitId);
    if (unit) {
      return normalizePathSelection(data, {
        selectedSectionId: section.id,
        selectedUnitId: unitId,
      });
    }
  }
  return null;
}
