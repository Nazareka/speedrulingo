import { Progress, ProgressIndicator } from "@radix-ui/react-progress";
import { motion, useReducedMotion } from "framer-motion";

import { progressBarCssWidth } from "./session-model";
import { FAST_TRANSITION } from "./ui-constants";

const MotionProgressIndicator = motion(ProgressIndicator);

type LessonTopBarProps = {
  /** Shown as `stepLabelIndex / totalCount` in the header (1-based step position). */
  stepLabelIndex: number;
  /** How many lesson steps are completed for the bar width (may equal `totalCount` on completion). */
  progressFillCompletedCount: number;
  totalCount: number;
  reviewCount: number;
  onBack: () => void;
};

export function LessonTopBar(props: LessonTopBarProps) {
  const { stepLabelIndex, progressFillCompletedCount, totalCount, reviewCount, onBack } = props;
  const safeTotal = Math.max(totalCount, 1);
  const progressValue = Math.min(Math.max(progressFillCompletedCount, 0), safeTotal);
  const progressWidth = progressBarCssWidth(progressFillCompletedCount, totalCount);
  const prefersReducedMotion = useReducedMotion();

  return (
    <header className="sticky top-0 z-30 border-[var(--lesson-border)] border-b bg-[color:var(--lesson-bg)]/96 backdrop-blur">
      <div className="mx-auto grid max-w-5xl grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3.5 md:px-6">
        <button
          className="inline-flex h-11 items-center gap-2 rounded-[1rem] border border-[var(--lesson-border-strong)] bg-[var(--lesson-surface)] px-4 font-medium text-[var(--lesson-text-muted)] text-sm transition hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface-muted)]"
          onClick={onBack}
          type="button"
        >
          <span aria-hidden="true">←</span>
          Leave
        </button>

        <div className="min-w-0">
          <Progress
            className="relative h-1.5 w-full overflow-hidden rounded-full bg-[var(--lesson-border-soft)]"
            getValueLabel={(value, max) =>
              `${value} of ${max} ${max === 1 ? "step" : "steps"} completed`
            }
            max={safeTotal}
            value={progressValue}
          >
            <MotionProgressIndicator
              animate={{ width: progressWidth }}
              className="h-full rounded-full bg-[var(--lesson-accent)]"
              initial={false}
              transition={prefersReducedMotion ? { duration: 0 } : FAST_TRANSITION}
            />
          </Progress>
        </div>

        <div className="shrink-0 text-right font-medium text-[var(--lesson-text-soft)] text-sm tabular-nums">
          {stepLabelIndex} / {totalCount} · Review {reviewCount}
        </div>
      </div>
    </header>
  );
}
