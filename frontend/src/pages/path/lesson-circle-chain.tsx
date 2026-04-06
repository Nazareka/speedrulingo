import { Link } from "@tanstack/react-router";
import { Check, Lock } from "lucide-react";
import { useMemo } from "react";

import type { LessonSummary } from "../../shared/api/generated/types.gen";

import { focusLessonIdForCircleChain, lessonChainRowVm } from "./lesson-circle-chain-vm";
import { sortLessonsByOrderIndex } from "./lesson-derive";

export function LessonCircleChain({
  lessons,
  currentLessonId,
  isApiActiveUnit,
  unitLocked,
}: {
  lessons: LessonSummary[];
  currentLessonId: string | null;
  isApiActiveUnit: boolean;
  /** Entire unit is locked (future path) — show chain with lock on every circle. */
  unitLocked: boolean;
}) {
  const ordered = useMemo(() => sortLessonsByOrderIndex(lessons), [lessons]);

  const focusLessonId = useMemo(
    () => focusLessonIdForCircleChain(ordered, currentLessonId, isApiActiveUnit, unitLocked),
    [ordered, currentLessonId, isApiActiveUnit, unitLocked],
  );

  if (ordered.length === 0) return null;

  return (
    <div className="mt-3 w-full min-w-0">
      <p className="mb-2 text-[10px] text-[var(--lesson-text-faint)] uppercase tracking-[0.2em]">
        Lessons
      </p>
      <ol
        aria-label="Lessons in this unit"
        className="m-0 flex w-full min-w-0 list-none flex-nowrap items-center gap-0 overflow-x-auto p-0 pb-1 [scrollbar-width:thin]"
      >
        {ordered.map((lesson, i) => {
          const prev = i > 0 ? (ordered[i - 1] ?? null) : null;
          const row = lessonChainRowVm(lesson, prev, focusLessonId, unitLocked);
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
            <li className="contents" key={lesson.id}>
              {connectorBefore !== null ? (
                <div
                  aria-hidden="true"
                  className={
                    connectorBefore.isGradient
                      ? "h-[3px] min-h-[3px] min-w-[4px] flex-1 self-center rounded-full"
                      : "h-[3px] min-h-[3px] min-w-[4px] flex-1 self-center rounded-full bg-[var(--lesson-border-soft)]"
                  }
                  style={connectorBefore.isGradient ? connectorBefore.style : undefined}
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
