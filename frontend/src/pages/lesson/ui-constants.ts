export const PRIMARY_BUTTON_CLASS =
  "rounded-[1rem] bg-[var(--lesson-accent)] px-7 py-3.5 font-semibold text-[0.95rem] text-white tracking-[-0.01em] shadow-[0_8px_18px_rgba(23,122,109,0.12)] transition hover:bg-[var(--lesson-accent-hover)] active:scale-[0.985]";

export const SECONDARY_BUTTON_CLASS =
  "rounded-[1rem] border border-[var(--lesson-border-strong)] bg-[var(--lesson-surface)] px-5 py-3 font-medium text-[var(--lesson-text-muted)] text-sm transition hover:bg-[var(--lesson-surface-muted)] active:scale-[0.985]";

export const FAST_TRANSITION = { duration: 0.1, ease: "easeOut" } as const;
export const QUICK_TRANSITION = { duration: 0.12, ease: "easeOut" } as const;
