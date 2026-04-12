import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

import { QUICK_TRANSITION } from "./ui-constants";

type LessonFeedbackOrCheckMotionZoneProps = {
  hasFeedback: boolean;
  feedbackSlot: ReactNode;
  checkSlot: ReactNode;
};

/** Swaps feedback vs check controls with the same motion pattern as the main lesson bottom zone. */
export function LessonFeedbackOrCheckMotionZone(props: LessonFeedbackOrCheckMotionZoneProps) {
  const { hasFeedback, feedbackSlot, checkSlot } = props;
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="mt-8 pt-2">
      <AnimatePresence initial={false} mode="wait">
        {hasFeedback ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 4 }}
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
            key="feedback-zone"
            transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
          >
            {feedbackSlot}
          </motion.div>
        ) : (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap items-center justify-end gap-3"
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 4 }}
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
            key="action-zone"
            transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
          >
            {checkSlot}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
