import type { FeedbackState } from "../../../entities/lesson/session-types";
import { PRIMARY_BUTTON_CLASS } from "../../../shared/ui/tokens/button-classes";
import { LessonFeedbackOrCheckMotionZone } from "./feedback-or-check-motion-zone";
import { LessonFeedbackTray } from "./feedback-tray";

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
  return (
    <LessonFeedbackOrCheckMotionZone
      checkSlot={
        props.feedback === null ? (
          <>
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
          </>
        ) : null
      }
      feedbackSlot={
        props.feedback !== null ? (
          <LessonFeedbackTray
            continueError={props.continueError}
            continuePending={props.continuePending}
            feedback={props.feedback}
            onContinue={props.onContinue}
          />
        ) : null
      }
      hasFeedback={props.feedback !== null}
    />
  );
}
