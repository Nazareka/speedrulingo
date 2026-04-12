import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from "@headlessui/react";
import { ChevronDown } from "lucide-react";
import { useMemo } from "react";

export type DropdownOption = {
  id: string;
  label: string;
  description?: string;
};

type DropdownPickerProps = {
  /** Text shown on the closed trigger. */
  label: string;
  value: string | null;
  options: DropdownOption[];
  onChange: (id: string) => void;
  /** Accessible name for the options panel (`role="listbox"`). */
  panelAriaLabel: string;
};

const optionById = (a: DropdownOption, b: DropdownOption) => a.id === b.id;

const triggerClass =
  "flex w-full min-w-0 max-w-full items-center justify-between gap-2 rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-3 py-2.5 text-left font-medium text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.06)] transition hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] outline-none ring-0 ring-offset-0 focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0";

const optionsPanelClass =
  "absolute top-[calc(100%+0.35rem)] right-0 left-0 z-[100] max-h-72 overflow-auto rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] py-1 shadow-[0_12px_32px_rgba(15,23,42,0.12)] outline-none ring-0 focus:outline-none focus:ring-0";

/**
 * Generic listbox-style dropdown: thin wrapper around Headless UI `Listbox` + Tailwind.
 * Open/close, focus, keyboard, outside click, and scroll-into-view for options are handled by Headless UI.
 */
export function DropdownPicker({
  label,
  value,
  options,
  onChange,
  panelAriaLabel,
}: DropdownPickerProps) {
  const selected = useMemo(() => options.find((o) => o.id === value) ?? null, [options, value]);

  return (
    <Listbox
      by={optionById}
      onChange={(opt) => {
        if (opt) onChange(opt.id);
      }}
      value={selected}
    >
      <div className="relative w-full min-w-0">
        <ListboxButton className={triggerClass}>
          {({ open }) => (
            <>
              <span className="min-w-0 flex-1 truncate text-sm">{label}</span>
              <ChevronDown
                aria-hidden="true"
                className={`h-4 w-4 shrink-0 text-[var(--lesson-text-muted)] transition-transform duration-200 ${
                  open ? "rotate-180" : ""
                }`}
              />
            </>
          )}
        </ListboxButton>
        <ListboxOptions
          aria-label={panelAriaLabel}
          className={optionsPanelClass}
          modal={false}
          portal={false}
          transition={false}
        >
          {options.map((opt) => {
            const hasDescription = opt.description !== undefined;
            return (
              <ListboxOption
                className={({ focus, selected }) =>
                  [
                    "w-full cursor-pointer px-3 py-2 text-left text-sm transition",
                    selected
                      ? "bg-[var(--lesson-accent-soft)] font-semibold text-[var(--lesson-accent)]"
                      : focus
                        ? "bg-[var(--lesson-surface-muted)] text-[var(--lesson-text)]"
                        : "text-[var(--lesson-text)] hover:bg-[var(--lesson-surface-muted)]",
                    hasDescription ? "flex flex-col items-start gap-0.5" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")
                }
                key={opt.id}
                value={opt}
              >
                {hasDescription ? (
                  <span className="text-[var(--lesson-text-faint)] text-xs">{opt.description}</span>
                ) : null}
                <span className={hasDescription ? "truncate font-medium" : "truncate"}>
                  {opt.label}
                </span>
              </ListboxOption>
            );
          })}
        </ListboxOptions>
      </div>
    </Listbox>
  );
}
