import { Link } from "@tanstack/react-router";
import { BookOpen, Play } from "lucide-react";
import { useState } from "react";

import { usePathQuery } from "../features/path/queries";
import type { SectionUnits } from "../shared/api/generated/types.gen";
import { useCurrentCourseQuery } from "../shared/auth/session";
import { SECONDARY_BUTTON_CLASS } from "../shared/ui/auth/auth-classes";

/** Compact primary for resume-learning card only (not full hero CTA). */
const RESUME_CONTINUE_CLASS =
  "inline-flex items-center gap-1.5 rounded-[0.65rem] bg-[var(--lesson-accent)] px-3 py-2 font-semibold text-sm text-white shadow-[0_2px_10px_rgba(37,99,235,0.22)] transition hover:bg-[var(--lesson-accent-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)] active:scale-[0.99]";

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function progressWidth(completed: number, total: number) {
  const safeTotal = Math.max(total, 1);
  const percent = (completed / safeTotal) * 100;
  return `${clamp(percent, 0, 100)}%`;
}

type SectionUnitsBlockProps = {
  section: SectionUnits;
  activeUnitId: string | null;
  isExpanded: boolean;
  onToggleExpand: () => void;
};

function SectionUnitsBlock({
  section,
  activeUnitId,
  isExpanded,
  onToggleExpand,
}: SectionUnitsBlockProps) {
  const orderedUnits = [...section.units].sort((a, b) => a.unit_order_index - b.unit_order_index);

  const activeUnitInSection =
    activeUnitId === null ? null : (orderedUnits.find((u) => u.id === activeUnitId) ?? null);

  const upcomingUnitsInSection = orderedUnits.filter(
    (u) => !u.is_locked && !u.is_completed && u.id !== activeUnitId,
  );

  const completedUnitsInSection = orderedUnits.filter(
    (u) => u.is_completed && u.id !== activeUnitId,
  );

  const lockedUnitsInSection = orderedUnits.filter((u) => u.is_locked && u.id !== activeUnitId);

  const previewUnits = activeUnitInSection
    ? [
        activeUnitInSection,
        ...upcomingUnitsInSection.slice(0, 2),
        ...lockedUnitsInSection.slice(0, 1),
        ...completedUnitsInSection.slice(0, 1),
      ]
    : orderedUnits.slice(0, 4);

  const hiddenUnitsCount = Math.max(0, orderedUnits.length - previewUnits.length);

  const expandedUnits = activeUnitInSection
    ? [
        activeUnitInSection,
        ...orderedUnits.filter(
          (u) =>
            u.id !== activeUnitInSection.id &&
            u.unit_order_index > activeUnitInSection.unit_order_index,
        ),
        ...orderedUnits.filter(
          (u) =>
            u.id !== activeUnitInSection.id &&
            u.unit_order_index < activeUnitInSection.unit_order_index,
        ),
      ]
    : orderedUnits;

  const unitsToRender = isExpanded ? expandedUnits : previewUnits;

  return (
    <div className="rounded-[1.8rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-4 md:p-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <h2 className="mt-0 font-semibold text-2xl tracking-[-0.03em]">{section.title}</h2>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {unitsToRender.map((unit) => {
          const isActive = unit.id === activeUnitId;

          const cardTone = unit.is_completed
            ? "border-[var(--lesson-success-border)] bg-[var(--lesson-success-bg)]"
            : unit.is_locked
              ? "border-[var(--lesson-border-soft)] bg-[var(--lesson-surface-muted)] text-[var(--lesson-text-soft)]"
              : isActive
                ? "border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)]"
                : "border-[var(--lesson-border)] bg-[var(--lesson-surface)]";

          const badgeTone = unit.is_completed
            ? "border border-[var(--lesson-success-border)] bg-[var(--lesson-success-bg)] text-[var(--lesson-text-muted)]"
            : unit.is_locked
              ? "border border-[var(--lesson-border-soft)] bg-[var(--lesson-surface-muted)] text-[var(--lesson-text-soft)]"
              : isActive
                ? "border border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] text-[var(--lesson-accent)]"
                : "border border-[var(--lesson-border-soft)] bg-[var(--lesson-surface-muted)] text-[var(--lesson-text-muted)]";

          const badgeText = unit.is_completed
            ? "Completed"
            : unit.is_locked
              ? "Locked"
              : isActive
                ? "Ready now"
                : "Upcoming";

          return (
            <article
              key={unit.id}
              className={`relative rounded-[1.6rem] border p-2.5 transition ${
                isActive ? "ring-1 ring-[var(--lesson-accent)]" : ""
              } ${cardTone}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[var(--lesson-text-faint)] text-xs uppercase tracking-[0.25em]">
                    Unit {unit.unit_order_index}
                  </p>
                  <h3 className="mt-0 truncate font-semibold text-[1.1rem] leading-tight">
                    {unit.title}
                  </h3>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs ${badgeTone}`}>
                  {badgeText}
                </span>
              </div>

              {unit.is_locked ? (
                <p className="mt-1.5 text-[var(--lesson-text-soft)] text-sm">
                  Locked until the section exam is cleared.
                </p>
              ) : (
                <>
                  {unit.is_completed ? (
                    <p className="mt-1.5 text-[var(--lesson-text-muted)] text-sm">
                      Review available.
                    </p>
                  ) : null}

                  <div className="mt-1.5">
                    {unit.is_completed ? (
                      <Link
                        className={`${SECONDARY_BUTTON_CLASS} w-full`}
                        params={{ unitId: unit.id }}
                        to="/unit/$unitId"
                      >
                        Review
                      </Link>
                    ) : isActive ? (
                      <Link
                        className={`${SECONDARY_BUTTON_CLASS} w-full`}
                        params={{ unitId: unit.id }}
                        to="/unit/$unitId"
                      >
                        Open unit
                      </Link>
                    ) : (
                      <Link
                        className={`${SECONDARY_BUTTON_CLASS} w-full`}
                        params={{ unitId: unit.id }}
                        to="/unit/$unitId"
                      >
                        Open unit
                      </Link>
                    )}
                  </div>
                </>
              )}
            </article>
          );
        })}
      </div>

      {hiddenUnitsCount > 0 ? (
        <div className="mt-3 flex justify-end">
          <button
            className={`${SECONDARY_BUTTON_CLASS} w-fit px-4 py-2`}
            onClick={onToggleExpand}
            type="button"
          >
            <span className="inline-flex items-center gap-2">
              <span>
                {isExpanded ? "Show fewer units" : `Show all ${orderedUnits.length} units`}
              </span>
              <svg
                aria-hidden="true"
                fill="none"
                height="16"
                viewBox="0 0 24 24"
                width="16"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d={isExpanded ? "M7 14l5-5 5 5" : "M7 10l5 5 5-5"}
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                />
              </svg>
            </span>
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function PathPage() {
  const pathQuery = usePathQuery();
  const currentCourseQuery = useCurrentCourseQuery();
  const activeUnitId = pathQuery.data?.current_unit_id ?? null;
  const [expandedBySectionId, setExpandedBySectionId] = useState<Record<string, boolean>>({});

  if (pathQuery.isLoading || currentCourseQuery.isLoading) {
    return (
      <div className="pt-4">
        <div className="mx-auto max-w-6xl space-y-6">
          <div className="h-28 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
          <div className="h-72 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="h-56 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
            <div className="h-56 animate-pulse rounded-[1.6rem] bg-[var(--lesson-surface-muted)]" />
          </div>
        </div>
      </div>
    );
  }

  if (!pathQuery.data || !currentCourseQuery.data) {
    return (
      <div className="pt-4 text-[var(--lesson-text-muted)]">
        <div className="mx-auto max-w-6xl rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-6">
          No active course is available yet.
        </div>
      </div>
    );
  }

  const allUnits = pathQuery.data.sections.flatMap((s) => s.units);
  const currentUnit =
    pathQuery.data.current_unit_id === null
      ? null
      : (allUnits.find((u) => u.id === pathQuery.data.current_unit_id) ?? null);

  const currentSection =
    currentUnit === null
      ? null
      : (pathQuery.data.sections.find((s) => s.id === currentUnit.section_id) ?? null);

  const allUnitsInCourseCompleted =
    pathQuery.data.sections.length > 0 &&
    pathQuery.data.sections.every(
      (s) => s.units.length > 0 && s.units.every((u) => u.is_completed),
    );

  const currentLessonId = pathQuery.data.current_lesson_id ?? null;

  const courseSections = pathQuery.data.sections;

  return (
    <div className="font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-[var(--lesson-text)]">
      <main className="mx-auto max-w-6xl py-5">
        <header className="mb-3">
          <h1 className="font-semibold text-2xl tracking-[-0.03em] md:text-3xl">Your path</h1>
          <p className="mt-1 text-[var(--lesson-text-muted)] text-sm">
            Pick up where you left off.
          </p>
        </header>

        <section className="w-full max-w-sm rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]">
          {currentUnit ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-[var(--lesson-text-faint)] text-xs">Continue learning</p>

              <h2 className="font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl">
                {currentSection?.title ?? "—"} Unit {currentUnit.unit_order_index}
              </h2>

              {currentLessonId && !currentUnit.is_completed ? (
                <p className="text-[var(--lesson-text-soft)] text-xs">Ready now</p>
              ) : null}

              <p className="text-[var(--lesson-text-muted)] text-sm">
                {currentUnit.completed_lessons} of {currentUnit.lesson_count} lessons completed
              </p>

              <div className="h-1.5 w-36 shrink-0 overflow-hidden rounded-full bg-[var(--lesson-border-soft)]">
                <div
                  className="h-full rounded-full bg-[var(--lesson-accent)]"
                  style={{
                    width: progressWidth(currentUnit.completed_lessons, currentUnit.lesson_count),
                  }}
                />
              </div>

              <div className="mt-1 flex justify-end border-[var(--lesson-border-soft)] border-t pt-2.5">
                {currentLessonId ? (
                  <Link
                    className={RESUME_CONTINUE_CLASS}
                    params={{ lessonId: currentLessonId }}
                    to="/lesson/$lessonId"
                  >
                    <Play aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                    Continue lesson
                  </Link>
                ) : (
                  <Link
                    className={RESUME_CONTINUE_CLASS}
                    params={{ unitId: currentUnit.id }}
                    to="/unit/$unitId"
                  >
                    <BookOpen aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                    Open unit
                  </Link>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <p className="text-[var(--lesson-text-faint)] text-xs">Continue learning</p>
              <h2 className="font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl">
                {currentCourseQuery.data.course_code} · v{currentCourseQuery.data.course_version}
              </h2>
              <p className="text-[var(--lesson-text-muted)] text-sm">
                {allUnitsInCourseCompleted
                  ? "You've completed every lesson. Review any unit below."
                  : "No active unit yet. Open your current section below to start."}
              </p>
            </div>
          )}
        </section>

        <div className="mt-4 space-y-4">
          <p className="font-mono text-[11px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
            Course path
          </p>
          {courseSections.map((section) => (
            <SectionUnitsBlock
              activeUnitId={activeUnitId}
              isExpanded={expandedBySectionId[section.id] ?? false}
              key={section.id}
              onToggleExpand={() =>
                setExpandedBySectionId((prev) => ({
                  ...prev,
                  [section.id]: !prev[section.id],
                }))
              }
              section={section}
            />
          ))}
        </div>

        <section className="mt-2 rounded-[1.4rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface-muted)] p-2 md:p-2">
          <p className="font-mono text-[9px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
            Unlocking
          </p>
          <p className="mt-0 text-[var(--lesson-text-muted)] text-sm">
            Finish the lessons and pass the exam to unlock what comes next.
          </p>
        </section>
      </main>
    </div>
  );
}
