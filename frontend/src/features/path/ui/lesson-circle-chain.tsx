import { Link } from "@tanstack/react-router";
import { Check, Lock } from "lucide-react";
import { useMemo } from "react";
import { sortLessonsByOrderIndex } from "../../../entities/path/unit-lessons";
import type { LessonSummary } from "../../../shared/api/generated/types.gen";
import { focusLessonIdForCircleChain, lessonChainRowVm } from "../model/lesson-circle-chain-vm";

export function LessonCircleChain({
  lessons,
  currentLessonId,
  isApiActiveUnit,
  unitLocked,
  orientation = "vertical",
  showLessonsLabel = false,
  verticalHeight,
}: {
  lessons: LessonSummary[];
  currentLessonId: string | null;
  isApiActiveUnit: boolean;
  /** Entire unit is locked (future path) — show chain with lock on every circle. */
  unitLocked: boolean;
  /** Horizontal = legacy row; vertical = Path unit stack (top → bottom). */
  orientation?: "horizontal" | "vertical";
  /** Path chain omits the “Lessons” caption. */
  showLessonsLabel?: boolean;
  /** Fixed vertical chain height; connector spacing expands/contracts to fill it. */
  verticalHeight?: number;
}) {
  const ordered = useMemo(() => sortLessonsByOrderIndex(lessons), [lessons]);

  const focusLessonId = useMemo(
    () => focusLessonIdForCircleChain(ordered, currentLessonId, isApiActiveUnit, unitLocked),
    [ordered, currentLessonId, isApiActiveUnit, unitLocked],
  );

  if (ordered.length === 0) return null;

  const isVertical = orientation === "vertical";
  const circleSize = 48;
  const naturalConnectorHeight = 14;
  const verticalConnectorHeight =
    isVertical && verticalHeight !== undefined && ordered.length > 1
      ? Math.max(
          (verticalHeight - ordered.length * circleSize) / (ordered.length - 1),
          naturalConnectorHeight,
        )
      : naturalConnectorHeight;
  const verticalListHeight =
    isVertical && verticalHeight !== undefined
      ? Math.max(verticalHeight, ordered.length * circleSize)
      : undefined;

  return (
    <div className={showLessonsLabel ? "mt-3 w-full min-w-0" : "w-full min-w-0"}>
      {showLessonsLabel ? (
        <p className="mb-2 text-[10px] text-[var(--lesson-text-faint)] uppercase tracking-[0.2em]">
          Lessons
        </p>
      ) : null}
      <ol
        aria-label="Lessons in this unit"
        className={
          isVertical
            ? "m-0 flex w-full min-w-0 list-none flex-col items-center gap-0 p-0 pb-1"
            : "m-0 flex w-full min-w-0 list-none flex-nowrap items-center gap-0 overflow-x-auto p-0 pb-1 [scrollbar-width:thin]"
        }
        style={
          isVertical && verticalListHeight !== undefined
            ? { height: verticalListHeight }
            : undefined
        }
      >
        {ordered.map((lesson, i) => {
          const prev = i > 0 ? (ordered[i - 1] ?? null) : null;
          const row = lessonChainRowVm(lesson, prev, focusLessonId, unitLocked, orientation);
          const {
            kindUi,
            isDone,
            isNext,
            title,
            connectorBefore,
            circleClassName,
            isInteractive,
            showLockIcon,
          } = row;

          const iconClass = "h-5 w-5 shrink-0";
          const KindIcon = kindUi.Icon;

          const circleBody = (
            <>
              {isDone && !unitLocked ? (
                <Check aria-hidden="true" className="h-5 w-5" strokeWidth={2.75} />
              ) : showLockIcon ? (
                <Lock aria-hidden="true" className="h-[1.125rem] w-[1.125rem]" strokeWidth={2.5} />
              ) : (
                <KindIcon aria-hidden="true" className={iconClass} strokeWidth={2} />
              )}
            </>
          );

          const node = isInteractive ? (
            <Link
              aria-current={isNext ? "step" : undefined}
              className={circleClassName}
              params={{ lessonId: lesson.id }}
              title={title}
              to="/lesson/$lessonId"
            >
              {circleBody}
            </Link>
          ) : (
            <span className={circleClassName} title={title}>
              {circleBody}
            </span>
          );

          return (
            <li className={isVertical ? "flex flex-col items-center" : "contents"} key={lesson.id}>
              {connectorBefore !== null ? (
                <div
                  aria-hidden="true"
                  className={
                    isVertical
                      ? connectorBefore.isGradient
                        ? "w-[3px] min-w-[3px] shrink-0 rounded-full"
                        : "w-[3px] min-w-[3px] shrink-0 rounded-full bg-[var(--lesson-border-soft)]"
                      : connectorBefore.isGradient
                        ? "h-[3px] min-h-[3px] min-w-[4px] flex-1 self-center rounded-full"
                        : "h-[3px] min-h-[3px] min-w-[4px] flex-1 self-center rounded-full bg-[var(--lesson-border-soft)]"
                  }
                  style={
                    isVertical
                      ? {
                          ...(connectorBefore.isGradient ? connectorBefore.style : {}),
                          height: verticalConnectorHeight,
                        }
                      : connectorBefore.isGradient
                        ? connectorBefore.style
                        : undefined
                  }
                />
              ) : null}
              <div className="relative shrink-0">{node}</div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
