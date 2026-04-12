import { WIDE_UNIT_NAV_BASE, WIDE_UNIT_NAV_INTERACTIVE } from "./unit-carousel.constants";

export function NavButton({
  label,
  ariaLabel,
  disabled,
  onClick,
}: {
  label: string;
  ariaLabel: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={ariaLabel}
      className={`relative z-10 ${WIDE_UNIT_NAV_BASE} ${disabled ? "" : WIDE_UNIT_NAV_INTERACTIVE}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}
