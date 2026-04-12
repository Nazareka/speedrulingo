import { useEffect, useRef } from "react";

import type { FeedbackState } from "../../../entities/lesson/session-types";
import {
  isLessonAnswerControlTarget,
  isSpaceTargetInsideInteractiveControl,
} from "../lib/shortcuts";

type UseLessonSpaceShortcutParams = {
  canCheck: boolean;
  feedback: FeedbackState | null;
  isLeaveDialogOpen: boolean;
  isLessonFinished: boolean;
  /** When true, Space is ignored (e.g. mutations in flight). */
  blockProgress: boolean;
  advanceQueue: () => void | Promise<void>;
  handleCheck: () => void | Promise<void>;
};

/**
 * Space → continue after feedback, or submit check when allowed (matches main + kana lesson UX).
 */
export function useLessonSpaceShortcut(params: UseLessonSpaceShortcutParams) {
  const {
    canCheck,
    feedback,
    isLeaveDialogOpen,
    isLessonFinished,
    blockProgress,
    advanceQueue,
    handleCheck,
  } = params;

  const advanceRef = useRef(advanceQueue);
  const checkRef = useRef(handleCheck);
  advanceRef.current = advanceQueue;
  checkRef.current = handleCheck;

  useEffect(() => {
    function handleWindowKeyDown(event: KeyboardEvent) {
      if (event.code !== "Space") {
        return;
      }

      if (isSpaceTargetInsideInteractiveControl(event.target)) {
        if (!(canCheck && feedback === null && isLessonAnswerControlTarget(event.target))) {
          return;
        }
      }

      if (isLeaveDialogOpen || isLessonFinished || blockProgress) {
        return;
      }

      if (feedback) {
        event.preventDefault();
        void advanceRef.current();
        return;
      }

      if (canCheck) {
        event.preventDefault();
        const active = document.activeElement;
        if (active instanceof HTMLElement && isLessonAnswerControlTarget(active)) {
          active.blur();
        }
        void checkRef.current();
      }
    }

    window.addEventListener("keydown", handleWindowKeyDown);
    return () => {
      window.removeEventListener("keydown", handleWindowKeyDown);
    };
  }, [canCheck, feedback, isLeaveDialogOpen, isLessonFinished, blockProgress]);
}
