import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { LessonFeedbackTray } from "./feedback-tray";
import type { FeedbackState } from "./session-types";
import { PRIMARY_BUTTON_CLASS, QUICK_TRANSITION } from "./ui-constants";

/** Parent decides feedback vs check phase; each branch only carries the props it needs. */
export type LessonBottomZoneProps =
  | {
      feedback: FeedbackState;
      onContinue: () => void;
      continuePending: boolean;
      continueError: string | null;
    }
  | {
      feedback: null;
      canCheck: boolean;
      onCheck: () => void;
      checkError: string | null;
      checkPending: boolean;
    };

export function LessonBottomZone(props: LessonBottomZoneProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="mt-8 pt-2">
      <AnimatePresence initial={false} mode="wait">
        {props.feedback !== null ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 4 }}
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
            key="feedback-zone"
            transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
          >
            <LessonFeedbackTray
              continueError={props.continueError}
              continuePending={props.continuePending}
              feedback={props.feedback}
              onContinue={props.onContinue}
            />
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
            {props.checkError ? (
              <span className="text-[var(--lesson-error-accent)] text-sm">{props.checkError}</span>
            ) : null}

            <button
              className={`min-w-[9.5rem] ${PRIMARY_BUTTON_CLASS} disabled:cursor-not-allowed disabled:bg-[var(--lesson-disabled-bg)]`}
              disabled={!props.canCheck}
              onClick={props.onCheck}
              type="button"
            >
              {props.checkPending ? "Checking..." : "Check"}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
