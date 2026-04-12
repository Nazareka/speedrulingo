import type { PathUnitSlide } from "../../../entities/path/model";
import type { SectionUnits } from "../../../shared/api/generated/types.gen";
import { type DropdownOption, DropdownPicker } from "./dropdown-picker";

/**
 * Path-specific adapters over `DropdownPicker` / flat rows.
 * Kept as thin wrappers so generic UI stays reusable; avoid adding more prop-only shims here.
 */

/** Maps course sections to generic dropdown options (path page adapter). */
export function SectionPicker({
  sections,
  currentSectionId,
  onSelectSection,
}: {
  sections: SectionUnits[];
  currentSectionId: string | null;
  onSelectSection: (sectionId: string) => void;
}) {
  const current = sections.find((s) => s.id === currentSectionId);
  const options: DropdownOption[] = sections.map((s) => ({
    id: s.id,
    label: s.title,
  }));

  return (
    <DropdownPicker
      label={current?.title ?? "Section"}
      onChange={onSelectSection}
      options={options}
      panelAriaLabel="Sections"
      value={currentSectionId}
    />
  );
}

/** Maps flat unit rows to generic dropdown options (path page adapter). */
export function AllUnitsPicker({
  allUnits,
  highlightedUnitId,
  onSelectUnit,
}: {
  allUnits: PathUnitSlide[];
  highlightedUnitId: string | null;
  onSelectUnit: (unitId: string) => void;
}) {
  const options: DropdownOption[] = allUnits.map(({ sectionTitle, unit }) => ({
    id: unit.id,
    label: unit.title,
    description: sectionTitle,
  }));

  return (
    <DropdownPicker
      label="All units"
      onChange={onSelectUnit}
      options={options}
      panelAriaLabel="All units"
      value={highlightedUnitId}
    />
  );
}
