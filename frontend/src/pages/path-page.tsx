import { Link } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  Check,
  ChevronDown,
  ChevronUp,
  GraduationCap,
  Lock,
  Play,
  ScrollText,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { usePathQuery } from "../features/path/queries";
import { useUnitDetailQuery } from "../features/units/queries";
import { UnitGuideCard } from "../features/units/unit-guide-card";
import type { LessonSummary, SectionUnits, UnitSummary } from "../shared/api/generated/types.gen";
import { useCurrentCourseQuery } from "../shared/auth/session";

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

/** First lesson the learner can open (prefer unlocked). */
function firstLessonIdForEntry(unit: UnitSummary): string | null {
  const { lessons } = unit;
  const head = lessons[0];
  if (head === undefined) return null;
  const firstOpen = lessons.find((l) => !l.is_locked);
  return (firstOpen ?? head).id;
}

function lessonKindLabel(kind: string): string {
  switch (kind) {
    case "normal":
      return "Lesson";
    case "review_previous_units":
      return "Review";
    case "exam":
      return "Exam";
    default:
      return kind.replaceAll("_", " ");
  }
}

function lessonStateLabel(state: string): string {
  switch (state) {
    case "completed":
      return "Completed";
    case "in_progress":
      return "In progress";
    case "not_started":
      return "Not started";
    default:
      return state;
  }
}

/** Light tint for all non-locked lesson circles (incomplete and completed). */
function lessonKindLightIncomplete(kind: string): string {
  switch (kind) {
    case "normal":
      return "border-[#bfdbfe] bg-[#eff6ff] text-[#1d4ed8]";
    case "review_previous_units":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "exam":
      return "border-rose-200 bg-rose-50 text-rose-900";
    default:
      return "border-[#bfdbfe] bg-[#eff6ff] text-[#1d4ed8]";
  }
}

function kindCompletedHex(kind: string): string {
  switch (kind) {
    case "normal":
      return "#2563eb";
    case "review_previous_units":
      return "#f59e0b";
    case "exam":
      return "#e11d48";
    default:
      return "#2563eb";
  }
}

/** Light fill used for incomplete circles — gradient tail when leaving a completed step. */
function kindLightFillHex(kind: string): string {
  switch (kind) {
    case "normal":
      return "#eff6ff";
    case "review_previous_units":
      return "#fffbeb";
    case "exam":
      return "#fff1f2";
    default:
      return "#eff6ff";
  }
}

function LessonKindIcon({ className, kind }: { className?: string; kind: string }) {
  const cn = className ?? "";
  switch (kind) {
    case "normal":
      return <BookOpen aria-hidden="true" className={cn} strokeWidth={2} />;
    case "review_previous_units":
      return <ScrollText aria-hidden="true" className={cn} strokeWidth={2} />;
    case "exam":
      return <GraduationCap aria-hidden="true" className={cn} strokeWidth={2} />;
    default:
      return <BookOpen aria-hidden="true" className={cn} strokeWidth={2} />;
  }
}

/**
 * Next lesson emphasis — inset-only glow (no outer box-shadow / scale).
 * The resume card uses overflow-hidden for slide transitions; outer shadows and transforms
 * were clipped to a rectangle, which looked like a square shadow.
 */
function nextLessonHighlightClass(kind: string): string {
  switch (kind) {
    case "normal":
      return "z-[1] shadow-[inset_0_0_0_2px_rgba(37,99,235,0.4),inset_0_2px_16px_rgba(37,99,235,0.2)]";
    case "review_previous_units":
      return "z-[1] shadow-[inset_0_0_0_2px_rgba(245,158,11,0.45),inset_0_2px_16px_rgba(245,158,11,0.22)]";
    case "exam":
      return "z-[1] shadow-[inset_0_0_0_2px_rgba(225,29,72,0.4),inset_0_2px_16px_rgba(225,29,72,0.18)]";
    default:
      return "z-[1] shadow-[inset_0_0_0_2px_rgba(37,99,235,0.4),inset_0_2px_16px_rgba(37,99,235,0.2)]";
  }
}

function LessonCircleChain({
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
  const ordered = useMemo(
    () => [...lessons].sort((a, b) => a.order_index - b.order_index),
    [lessons],
  );

  const focusLessonId = useMemo(() => {
    if (unitLocked) return null;
    if (ordered.length === 0) return null;
    if (isApiActiveUnit && currentLessonId && ordered.some((l) => l.id === currentLessonId)) {
      return currentLessonId;
    }
    const next = ordered.find((l) => l.state !== "completed");
    return next?.id ?? null;
  }, [ordered, currentLessonId, isApiActiveUnit, unitLocked]);

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
          const isDone = lesson.state === "completed";
          const isNext = !unitLocked && !isDone && lesson.id === focusLessonId;
          const light = lessonKindLightIncomplete(lesson.kind);
          const locked = lesson.is_locked && !isDone;
          const showLockIcon = unitLocked || locked;
          const title = `${lessonKindLabel(lesson.kind)} · ${lessonStateLabel(lesson.state)}${
            unitLocked ? " · Unit locked" : locked ? " · Locked until prerequisites are met" : ""
          }`;

          const prev: LessonSummary | null = i > 0 ? (ordered[i - 1] ?? null) : null;
          const bothCompleted =
            !unitLocked &&
            prev !== null &&
            prev.state === "completed" &&
            lesson.state === "completed";
          const completedToNext =
            !unitLocked &&
            prev !== null &&
            prev.state === "completed" &&
            lesson.state !== "completed";

          const connectorStyle: CSSProperties | undefined = (() => {
            if (!prev) return undefined;
            if (bothCompleted) {
              return {
                backgroundImage: `linear-gradient(90deg, ${kindCompletedHex(prev.kind)}, ${kindCompletedHex(lesson.kind)})`,
              };
            }
            if (completedToNext) {
              return {
                backgroundImage: `linear-gradient(90deg, ${kindCompletedHex(prev.kind)}, ${kindLightFillHex(lesson.kind)})`,
              };
            }
            return undefined;
          })();

          const connectorIsGradient = bothCompleted || completedToNext;

          const iconClass = "h-5 w-5 shrink-0";

          const circleBody = (
            <>
              {isDone && !unitLocked ? (
                <Check aria-hidden="true" className="h-5 w-5" strokeWidth={2.75} />
              ) : showLockIcon ? (
                <Lock aria-hidden="true" className="h-[1.125rem] w-[1.125rem]" strokeWidth={2.5} />
              ) : (
                <LessonKindIcon className={iconClass} kind={lesson.kind} />
              )}
            </>
          );

          const circleClassName = [
            "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 text-[11px] leading-none transition duration-200",
            light,
            unitLocked || locked ? "opacity-[0.55] grayscale-[0.15]" : "",
            !isDone && !locked && !unitLocked && isNext
              ? nextLessonHighlightClass(lesson.kind)
              : "",
          ]
            .filter(Boolean)
            .join(" ");

          const node =
            !unitLocked && !locked ? (
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
              {i > 0 ? (
                <div
                  aria-hidden="true"
                  className={
                    connectorIsGradient
                      ? "h-[3px] min-h-[3px] min-w-[4px] flex-1 self-center rounded-full"
                      : "h-[3px] min-h-[3px] min-w-[4px] flex-1 self-center rounded-full bg-[var(--lesson-border-soft)]"
                  }
                  style={connectorIsGradient ? connectorStyle : undefined}
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

type PathUnitSlide = { sectionTitle: string; unit: UnitSummary };

const resumeSlideEase = [0.22, 1, 0.36, 1] as const;

const resumeSlideVariants = {
  enter: (dir: number) => ({
    y: dir > 0 ? 32 : dir < 0 ? -32 : 0,
    opacity: 0,
    filter: "blur(4px)",
  }),
  center: {
    y: 0,
    opacity: 1,
    filter: "blur(0px)",
  },
  exit: (dir: number) => ({
    y: dir > 0 ? -32 : dir < 0 ? 32 : 0,
    opacity: 0,
    filter: "blur(4px)",
  }),
};

function ResumeSlideInner({
  sectionTitle,
  unit,
  currentLessonId,
  isApiActiveUnit,
}: {
  sectionTitle: string;
  unit: UnitSummary;
  currentLessonId: string | null;
  isApiActiveUnit: boolean;
}) {
  const lessonReady =
    isApiActiveUnit && currentLessonId !== null && !unit.is_completed && !unit.is_locked;
  const entryLessonId = firstLessonIdForEntry(unit);

  return (
    <div className="flex flex-col gap-1.5">
      <h2 className="font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl">
        {sectionTitle} Unit {unit.unit_order_index}
      </h2>

      {unit.is_locked ? (
        <>
          <p className="text-[var(--lesson-text-soft)] text-sm">
            Locked until the section exam is cleared.
          </p>
          {unit.lessons.length > 0 ? (
            <LessonCircleChain
              currentLessonId={currentLessonId}
              isApiActiveUnit={isApiActiveUnit}
              lessons={unit.lessons}
              unitLocked
            />
          ) : null}
        </>
      ) : (
        <>
          {unit.is_completed ? (
            <p className="text-[var(--lesson-text-muted)] text-sm">Review available.</p>
          ) : null}

          {unit.lessons.length > 0 ? (
            <LessonCircleChain
              currentLessonId={currentLessonId}
              isApiActiveUnit={isApiActiveUnit}
              lessons={unit.lessons}
              unitLocked={false}
            />
          ) : !unit.is_completed ? (
            <div className="mt-2 h-1.5 w-36 shrink-0 overflow-hidden rounded-full bg-[var(--lesson-border-soft)]">
              <div
                className="h-full rounded-full bg-[var(--lesson-accent)]"
                style={{
                  width: progressWidth(unit.completed_lessons, unit.lesson_count),
                }}
              />
            </div>
          ) : null}

          <div className="mt-2 flex justify-end border-[var(--lesson-border-soft)] border-t pt-2.5">
            {lessonReady && currentLessonId ? (
              <Link
                className={RESUME_CONTINUE_CLASS}
                params={{ lessonId: currentLessonId }}
                to="/lesson/$lessonId"
              >
                <Play aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                Continue lesson
              </Link>
            ) : entryLessonId ? (
              <Link
                className={RESUME_CONTINUE_CLASS}
                params={{ lessonId: entryLessonId }}
                to="/lesson/$lessonId"
              >
                <BookOpen aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                {unit.is_completed ? "Review" : "Open unit"}
              </Link>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function ContinueLearningSelector({
  slides,
  activeUnitId,
  currentLessonId,
  fallbackTitle,
  fallbackBody,
  onSlideUnitChange,
  focusUnitId,
  onFocusUnitConsumed,
  sidePanel,
}: {
  slides: PathUnitSlide[];
  activeUnitId: string | null;
  currentLessonId: string | null;
  fallbackTitle: string;
  fallbackBody: string;
  onSlideUnitChange?: (unitId: string | null) => void;
  focusUnitId?: string | null;
  onFocusUnitConsumed?: () => void;
  /** Renders beside the lesson card (md+); chevrons stay in the left column only. */
  sidePanel?: ReactNode;
}) {
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(0);
  const skipNextSlideSync = useRef(false);

  useEffect(() => {
    if (slides.length === 0) return;
    if (focusUnitId != null) {
      const jump = slides.findIndex((s) => s.unit.id === focusUnitId);
      if (jump >= 0) {
        setIndex(jump);
        skipNextSlideSync.current = true;
        onFocusUnitConsumed?.();
        return;
      }
    }
    if (skipNextSlideSync.current) {
      skipNextSlideSync.current = false;
      return;
    }
    const next = activeUnitId !== null ? slides.findIndex((s) => s.unit.id === activeUnitId) : -1;
    setIndex(next >= 0 ? next : 0);
  }, [activeUnitId, focusUnitId, onFocusUnitConsumed, slides]);

  const count = slides.length;
  const canGoUp = index > 0;
  const canGoDown = index < count - 1;
  const slide = count > 0 ? slides[clamp(index, 0, count - 1)] : undefined;

  useEffect(() => {
    if (slides.length === 0) {
      onSlideUnitChange?.(null);
      return;
    }
    onSlideUnitChange?.(slide?.unit.id ?? null);
  }, [slide?.unit.id, slides.length, onSlideUnitChange]);

  const goPrev = () => {
    if (!canGoUp) return;
    setDirection(-1);
    setIndex((i) => i - 1);
  };

  const goNext = () => {
    if (!canGoDown) return;
    setDirection(1);
    setIndex((i) => i + 1);
  };

  const roundNavClass =
    "flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-[var(--lesson-border)] bg-[var(--lesson-surface)] text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.08)] transition hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:border-[var(--lesson-border)] disabled:hover:bg-[var(--lesson-surface)]";

  if (count === 0 || slide === undefined) {
    if (sidePanel) {
      return (
        <div className="grid w-full min-w-0 grid-cols-1 items-start gap-6 md:grid-cols-2 md:gap-8">
          <section className="w-full rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]">
            <div className="flex flex-col gap-1.5">
              <h2 className="font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl">
                {fallbackTitle}
              </h2>
              <p className="text-[var(--lesson-text-muted)] text-sm">{fallbackBody}</p>
            </div>
          </section>
          <div className="hidden min-h-0 min-w-0 md:block">{sidePanel}</div>
        </div>
      );
    }
    return (
      <section className="w-full rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]">
        <div className="flex flex-col gap-1.5">
          <h2 className="font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl">
            {fallbackTitle}
          </h2>
          <p className="text-[var(--lesson-text-muted)] text-sm">{fallbackBody}</p>
        </div>
      </section>
    );
  }

  const carouselCard = (
    <div className="relative min-h-[18.5rem] w-full min-w-0 overflow-hidden rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]">
      <AnimatePresence custom={direction} initial={false} mode="wait">
        <motion.div
          animate="center"
          className="top-0 left-0 w-full"
          custom={direction}
          exit="exit"
          initial="enter"
          key={slide.unit.id}
          transition={{ duration: 0.34, ease: resumeSlideEase }}
          variants={resumeSlideVariants}
        >
          <ResumeSlideInner
            currentLessonId={currentLessonId}
            isApiActiveUnit={slide.unit.id === activeUnitId}
            sectionTitle={slide.sectionTitle}
            unit={slide.unit}
          />
        </motion.div>
      </AnimatePresence>
    </div>
  );

  if (sidePanel) {
    return (
      <section className="flex w-full flex-col items-center gap-2 md:grid md:grid-cols-2 md:items-start md:gap-x-8 md:gap-y-2">
        <motion.button
          aria-label="Previous unit"
          className={`order-1 ${roundNavClass} md:col-start-1 md:row-start-1 md:justify-self-center`}
          disabled={!canGoUp}
          onClick={goPrev}
          transition={{ type: "spring", stiffness: 420, damping: 28 }}
          type="button"
          {...(canGoUp ? { whileTap: { scale: 0.92 } } : {})}
        >
          <ChevronUp aria-hidden="true" className="h-5 w-5" strokeWidth={2.25} />
        </motion.button>

        <div className="order-2 w-full min-w-0 md:col-start-1 md:row-start-2">{carouselCard}</div>

        <div className="order-5 hidden min-h-0 w-full min-w-0 md:order-none md:col-start-2 md:row-span-3 md:row-start-2 md:block md:self-start">
          {sidePanel}
        </div>

        <motion.button
          aria-label="Next unit"
          className={`order-3 ${roundNavClass} md:col-start-1 md:row-start-3 md:justify-self-center`}
          disabled={!canGoDown}
          onClick={goNext}
          transition={{ type: "spring", stiffness: 420, damping: 28 }}
          type="button"
          {...(canGoDown ? { whileTap: { scale: 0.92 } } : {})}
        >
          <ChevronDown aria-hidden="true" className="h-5 w-5" strokeWidth={2.25} />
        </motion.button>

        <p className="order-4 text-[var(--lesson-text-muted)] text-xs tabular-nums md:col-start-1 md:row-start-4">
          {index + 1} / {count}
        </p>
      </section>
    );
  }

  return (
    <section className="flex w-full flex-col items-center gap-2">
      <motion.button
        aria-label="Previous unit"
        className={roundNavClass}
        disabled={!canGoUp}
        onClick={goPrev}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
        type="button"
        {...(canGoUp ? { whileTap: { scale: 0.92 } } : {})}
      >
        <ChevronUp aria-hidden="true" className="h-5 w-5" strokeWidth={2.25} />
      </motion.button>

      {carouselCard}

      <motion.button
        aria-label="Next unit"
        className={roundNavClass}
        disabled={!canGoDown}
        onClick={goNext}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
        type="button"
        {...(canGoDown ? { whileTap: { scale: 0.92 } } : {})}
      >
        <ChevronDown aria-hidden="true" className="h-5 w-5" strokeWidth={2.25} />
      </motion.button>

      <p className="text-[var(--lesson-text-muted)] text-xs tabular-nums">
        {index + 1} / {count}
      </p>
    </section>
  );
}

function SectionPicker({
  sections,
  currentSectionId,
  onSelectSection,
}: {
  sections: SectionUnits[];
  currentSectionId: string | null;
  onSelectSection: (sectionId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handlePointer = (e: MouseEvent | PointerEvent) => {
      if (containerRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointer);
    return () => document.removeEventListener("pointerdown", handlePointer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const current = sections.find((s) => s.id === currentSectionId);

  return (
    <div className="relative w-full min-w-0" ref={containerRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex w-full min-w-0 max-w-full items-center justify-between gap-2 rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-3 py-2.5 text-left font-medium text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.06)] transition hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)]"
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        <span className="min-w-0 flex-1 truncate text-sm">{current?.title ?? "Section"}</span>
        <ChevronDown
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-[var(--lesson-text-muted)] transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open ? (
        <div
          aria-label="Sections"
          className="absolute top-[calc(100%+0.35rem)] right-0 left-0 z-[100] max-h-60 overflow-auto rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] py-1 shadow-[0_12px_32px_rgba(15,23,42,0.12)]"
          role="listbox"
        >
          {sections.map((section) => {
            const selected = section.id === currentSectionId;
            return (
              <button
                aria-selected={selected}
                className={`w-full px-3 py-2 text-left text-sm transition ${
                  selected
                    ? "bg-[var(--lesson-accent-soft)] font-semibold text-[var(--lesson-accent)]"
                    : "text-[var(--lesson-text)] hover:bg-[var(--lesson-surface-muted)]"
                }`}
                key={section.id}
                onClick={() => {
                  onSelectSection(section.id);
                  setOpen(false);
                }}
                role="option"
                type="button"
              >
                {section.title}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function AllUnitsPicker({
  allUnits,
  highlightedUnitId,
  onSelectUnit,
}: {
  allUnits: PathUnitSlide[];
  highlightedUnitId: string | null;
  onSelectUnit: (unitId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handlePointer = (e: MouseEvent | PointerEvent) => {
      if (containerRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", handlePointer);
    return () => document.removeEventListener("pointerdown", handlePointer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="relative w-full min-w-0" ref={containerRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex w-full min-w-0 max-w-full items-center justify-between gap-2 rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-3 py-2.5 text-left font-medium text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.06)] transition hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)]"
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        <span className="min-w-0 flex-1 truncate text-sm">All units</span>
        <ChevronDown
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-[var(--lesson-text-muted)] transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open ? (
        <div
          aria-label="All units"
          className="absolute top-[calc(100%+0.35rem)] right-0 left-0 z-[100] max-h-72 overflow-auto rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] py-1 shadow-[0_12px_32px_rgba(15,23,42,0.12)]"
          role="listbox"
        >
          {allUnits.map(({ sectionTitle, unit }) => {
            const selected = unit.id === highlightedUnitId;
            return (
              <button
                aria-selected={selected}
                className={`flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm transition ${
                  selected
                    ? "bg-[var(--lesson-accent-soft)] font-semibold text-[var(--lesson-accent)]"
                    : "text-[var(--lesson-text)] hover:bg-[var(--lesson-surface-muted)]"
                }`}
                key={unit.id}
                onClick={() => {
                  onSelectUnit(unit.id);
                  setOpen(false);
                }}
                role="option"
                type="button"
              >
                <span className="text-[var(--lesson-text-faint)] text-xs">{sectionTitle}</span>
                <span className="truncate font-medium">{unit.title}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function PathPage() {
  const pathQuery = usePathQuery();
  const currentCourseQuery = useCurrentCourseQuery();
  const activeUnitId = pathQuery.data?.current_unit_id ?? null;
  const [pickedSectionId, setPickedSectionId] = useState<string | null>(null);
  const [pendingFocusUnitId, setPendingFocusUnitId] = useState<string | null>(null);
  const [carouselUnitId, setCarouselUnitId] = useState<string | null>(null);

  const sectionIdFromActiveUnit = useMemo(() => {
    if (!pathQuery.data) return null;
    const secs = pathQuery.data.sections;
    if (activeUnitId) {
      for (const s of secs) {
        if (s.units.some((u) => u.id === activeUnitId)) return s.id;
      }
    }
    return secs[0]?.id ?? null;
  }, [pathQuery.data, activeUnitId]);

  useEffect(() => {
    setPickedSectionId(null);
  }, []);

  const effectiveSectionId = pickedSectionId ?? sectionIdFromActiveUnit;

  const pathSlides: PathUnitSlide[] = useMemo(() => {
    if (!pathQuery.data || !effectiveSectionId) return [];
    const section = pathQuery.data.sections.find((s) => s.id === effectiveSectionId);
    if (!section) return [];
    return [...section.units]
      .sort((a, b) => a.unit_order_index - b.unit_order_index)
      .map((unit) => ({ sectionTitle: section.title, unit }));
  }, [pathQuery.data, effectiveSectionId]);

  const allUnitsFlat: PathUnitSlide[] = useMemo(() => {
    if (!pathQuery.data) return [];
    return pathQuery.data.sections.flatMap((section) =>
      [...section.units]
        .sort((a, b) => a.unit_order_index - b.unit_order_index)
        .map((unit) => ({ sectionTitle: section.title, unit })),
    );
  }, [pathQuery.data]);

  const guideUnitId = useMemo(
    () => carouselUnitId ?? activeUnitId ?? pathSlides[0]?.unit.id ?? null,
    [carouselUnitId, activeUnitId, pathSlides],
  );
  const guideUnitQuery = useUnitDetailQuery(guideUnitId);

  const handleFocusConsumed = useCallback(() => {
    setPendingFocusUnitId(null);
  }, []);

  const handlePickUnitFromAll = useCallback(
    (unitId: string) => {
      const row = allUnitsFlat.find((u) => u.unit.id === unitId);
      if (!row) return;
      setPickedSectionId(row.unit.section_id);
      setPendingFocusUnitId(unitId);
    },
    [allUnitsFlat],
  );

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

  const allUnitsInCourseCompleted =
    pathQuery.data.sections.length > 0 &&
    pathQuery.data.sections.every(
      (s) => s.units.length > 0 && s.units.every((u) => u.is_completed),
    );

  const currentLessonId = pathQuery.data.current_lesson_id ?? null;

  const courseSections = pathQuery.data.sections;
  const currentSection =
    effectiveSectionId != null
      ? (courseSections.find((s) => s.id === effectiveSectionId) ?? null)
      : null;

  return (
    <div className="font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-[var(--lesson-text)]">
      <main className="mx-auto w-full max-w-6xl py-5">
        <div className="space-y-4">
          <header>
            <h1 className="font-semibold text-2xl tracking-[-0.03em] md:text-3xl">Your path</h1>
            <p className="mt-1 text-[var(--lesson-text-muted)] text-sm">
              Pick up where you left off.
            </p>
          </header>

          <div className="w-full min-w-0 space-y-2">
            {courseSections.length > 0 ? (
              <div className="w-full min-w-0 md:grid md:grid-cols-2 md:items-start md:gap-x-8">
                <div className="grid min-w-0 grid-cols-2 gap-2">
                  <div className="min-w-0">
                    <SectionPicker
                      currentSectionId={effectiveSectionId}
                      onSelectSection={setPickedSectionId}
                      sections={courseSections}
                    />
                  </div>
                  <div className="min-w-0">
                    <AllUnitsPicker
                      allUnits={allUnitsFlat}
                      highlightedUnitId={carouselUnitId ?? activeUnitId}
                      onSelectUnit={handlePickUnitFromAll}
                    />
                  </div>
                </div>
                <div aria-hidden="true" className="hidden min-h-0 md:block" />
              </div>
            ) : null}
          </div>

          <ContinueLearningSelector
            activeUnitId={activeUnitId}
            currentLessonId={currentLessonId}
            fallbackBody={
              allUnitsInCourseCompleted
                ? "You've completed every lesson. Browse units in the carousel below."
                : "No active unit yet. Choose a section to browse units."
            }
            fallbackTitle={`${currentCourseQuery.data.course_code} · v${currentCourseQuery.data.course_version}`}
            focusUnitId={pendingFocusUnitId}
            onFocusUnitConsumed={handleFocusConsumed}
            onSlideUnitChange={setCarouselUnitId}
            sidePanel={
              <aside aria-label="Unit guide for the selected unit">
                {!guideUnitId ? (
                  <p className="text-[var(--lesson-text-muted)] text-sm">
                    Select a unit in the carousel to see its guide.
                  </p>
                ) : guideUnitQuery.isLoading ? (
                  <div className="h-80 animate-pulse rounded-[1.75rem] bg-[var(--lesson-surface-muted)]" />
                ) : guideUnitQuery.data ? (
                  <UnitGuideCard unit={guideUnitQuery.data} />
                ) : (
                  <p className="text-[var(--lesson-text-muted)] text-sm">
                    Guide could not be loaded.
                  </p>
                )}
              </aside>
            }
            slides={pathSlides}
          />

          <section className="rounded-[1.4rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface-muted)] p-3 md:p-4">
            <p className="font-semibold text-[var(--lesson-text)] text-base leading-snug">
              {currentSection?.title ?? "Section"}
            </p>
            {currentSection?.description.trim() ? (
              <p className="mt-2 text-[var(--lesson-text-muted)] text-sm leading-relaxed">
                {currentSection.description}
              </p>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}
