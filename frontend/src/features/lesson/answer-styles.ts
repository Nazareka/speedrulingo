import type { FeedbackState } from "../../shared/lesson/session-types";

export function answerStateClasses(
  isSelected: boolean,
  feedback: FeedbackState | null,
  option: string,
  expectedAnswer: string,
) {
  if (!feedback) {
    return isSelected
      ? "border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] text-[var(--lesson-text)] shadow-[0_12px_26px_rgba(23,122,109,0.10)]"
      : "border-[var(--lesson-border)] bg-[var(--lesson-surface)] text-[var(--lesson-text)] hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface)] hover:shadow-[0_10px_22px_rgba(35,48,54,0.05)]";
  }

  if (option === expectedAnswer) {
    return "border-[var(--lesson-success-border)] bg-[var(--lesson-success-bg)] text-[var(--lesson-text)] shadow-[0_10px_20px_rgba(76,141,118,0.07)]";
  }

  if (isSelected && !feedback.isCorrect) {
    return "border-[var(--lesson-error-border)] bg-[var(--lesson-error-bg)] text-[var(--lesson-text)] shadow-[0_10px_20px_rgba(170,112,92,0.06)]";
  }

  return "border-[var(--lesson-border-soft)] bg-[var(--lesson-muted-bg)] text-[var(--lesson-muted-text)]";
}
