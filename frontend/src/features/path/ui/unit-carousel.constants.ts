import type { PathUnitSlide } from "../../../entities/path/model";

export function unitCarouselLabel(slide: PathUnitSlide): string {
  const t = slide.unit.title.trim();
  return t.length > 0 ? t : `${slide.sectionTitle} Unit ${slide.unit.unit_order_index}`;
}

/** Shared surface card shell (empty state + carousel viewport). */
export const PATH_UNIT_SURFACE_CARD =
  "rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]";

/** Unit carousel card title (fallback empty state + active slide). */
export const PATH_UNIT_CARD_TITLE =
  "font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl";
export const PATH_FALLBACK_BODY = "text-[var(--lesson-text-muted)] text-sm";

export const PATH_CAROUSEL_INDEX = "text-[var(--lesson-text-muted)] text-xs tabular-nums";

export const WIDE_UNIT_NAV_BASE =
  "w-full min-w-0 rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-3 py-2.5 text-left font-medium text-sm text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.06)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-[var(--lesson-border)] disabled:hover:bg-[var(--lesson-surface)]";

export const WIDE_UNIT_NAV_INTERACTIVE =
  "hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] active:scale-[0.99]";

export const WIDE_UNIT_NAV_CURRENT =
  "w-full min-w-0 rounded-xl border-2 border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] px-3 py-2.5 text-left font-semibold text-sm text-[var(--lesson-text)] shadow-[0_2px_10px_rgba(37,99,235,0.12)]";

/** Short vertical spine connecting prev and current buttons. */
export const UNIT_NAV_DASHED_SHORT =
  "h-4 w-[3px] shrink-0 rounded-full bg-[var(--lesson-border-soft)]";

/** Vertical segment matching lesson connectors — links unit blocks into one path. */
export const CHAIN_SPINE =
  "h-[14px] min-h-[14px] w-[3px] shrink-0 rounded-full bg-[var(--lesson-border-soft)]";

export const PATH_UNIT_SWAP_EASE = [0.22, 1, 0.36, 1] as const;
export const PATH_UNIT_CHAIN_DURATION = 0.62;
export const CHAIN_BRIDGE_HEIGHT = 14;
export const CHAIN_ANIMATION_MS = 700;
export const CHAIN_NODE_SIZE = 48;
export const CHAIN_MIN_CONNECTOR = 14;
export const CHAIN_END_SPINES = 28;

export type ChainTransitionState = {
  id: number;
  from: PathUnitSlide;
  to: PathUnitSlide;
  direction: number;
};
