import type { CSSProperties } from "react";

import type { LessonSummary } from "../../shared/api/generated/types.gen";

import { getLessonKindUi, getLessonStateLabel, type LessonKindUi } from "./lesson-ui";

/** Connector segment between two lesson nodes (gradient or default track). */
type LessonChainConnectorVm = {
  isGradient: boolean;
  style: CSSProperties | undefined;
};

/** One row in the lesson circle chain (pure data for rendering). */
type LessonChainRowVm = {
  kindUi: LessonKindUi;
  isDone: boolean;
  isNext: boolean;
  title: string;
  /** Connector before this node; `null` for the first lesson. */
  connectorBefore: LessonChainConnectorVm | null;
  circleClassName: string;
  isInteractive: boolean;
  showLockIcon: boolean;
};

export function lessonChainRowVm(
  lesson: LessonSummary,
  prev: LessonSummary | null,
  focusLessonId: string | null,
  unitLocked: boolean,
  orientation: "horizontal" | "vertical" = "horizontal",
): LessonChainRowVm {
  const gradientDeg = orientation === "vertical" ? "180deg" : "90deg";
  const kindUi = getLessonKindUi(lesson.kind);
  const isDone = lesson.state === "completed";
  const isNext = !unitLocked && !isDone && lesson.id === focusLessonId;
  const locked = lesson.is_locked && !isDone;
  const showLockIcon = unitLocked || locked;
  const title = `${kindUi.label} · ${getLessonStateLabel(lesson.state)}${
    unitLocked ? " · Unit locked" : locked ? " · Locked until prerequisites are met" : ""
  }`;

  let connectorBefore: LessonChainConnectorVm | null = null;
  if (prev !== null) {
    const prevKindUi = getLessonKindUi(prev.kind);
    const bothCompleted = !unitLocked && prev.state === "completed" && lesson.state === "completed";
    const completedToNext =
      !unitLocked && prev.state === "completed" && lesson.state !== "completed";

    if (bothCompleted) {
      connectorBefore = {
        isGradient: true,
        style: {
          backgroundImage: `linear-gradient(${gradientDeg}, ${prevKindUi.completedHex}, ${kindUi.completedHex})`,
        },
      };
    } else if (completedToNext) {
      connectorBefore = {
        isGradient: true,
        style: {
          backgroundImage: `linear-gradient(${gradientDeg}, ${prevKindUi.completedHex}, ${kindUi.lightFillHex})`,
        },
      };
    } else {
      connectorBefore = { isGradient: false, style: undefined };
    }
  }

  const circleClassName = [
    "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 text-[11px] leading-none transition duration-200",
    kindUi.incompleteCircleClass,
    unitLocked || locked ? "opacity-[0.55] grayscale-[0.15]" : "",
    !isDone && !locked && !unitLocked && isNext ? kindUi.nextHighlightClass : "",
  ]
    .filter(Boolean)
    .join(" ");

  return {
    kindUi,
    isDone,
    isNext,
    title,
    connectorBefore,
    circleClassName,
    isInteractive: !unitLocked && !locked,
    showLockIcon,
  };
}

/**
 * Lesson id that receives the “next step” highlight: API current lesson when it belongs to this
 * chain, otherwise the first incomplete lesson in `order_index` order.
 */
export function focusLessonIdForCircleChain(
  ordered: LessonSummary[],
  currentLessonId: string | null,
  isApiActiveUnit: boolean,
  unitLocked: boolean,
): string | null {
  if (unitLocked) return null;
  if (ordered.length === 0) return null;
  if (isApiActiveUnit && currentLessonId && ordered.some((l) => l.id === currentLessonId)) {
    return currentLessonId;
  }
  const next = ordered.find((l) => l.state !== "completed");
  return next?.id ?? null;
}
