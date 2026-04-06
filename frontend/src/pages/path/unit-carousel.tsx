import { Link } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, ChevronDown, ChevronUp, Play } from "lucide-react";
import type { ReactNode } from "react";
import { useLayoutEffect, useMemo, useRef, useState } from "react";

import type { UnitSummary } from "../../shared/api/generated/types.gen";

import { LessonCircleChain } from "./lesson-circle-chain";
import { firstLessonIdForEntry, progressWidthPercent } from "./lesson-derive";
import type { PathUnitSlide } from "./model";

/** Compact primary for resume-learning card only (not full hero CTA). */
const RESUME_CONTINUE_CLASS =
  "inline-flex items-center gap-1.5 rounded-[0.65rem] bg-[var(--lesson-accent)] px-3 py-2 font-semibold text-sm text-white shadow-[0_2px_10px_rgba(37,99,235,0.22)] transition hover:bg-[var(--lesson-accent-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)] active:scale-[0.99]";

/** Shared surface card shell (empty state + carousel viewport). */
const PATH_UNIT_SURFACE_CARD =
  "rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]";

/** Unit carousel card title (fallback empty state + active slide). */
const PATH_UNIT_CARD_TITLE =
  "font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl";
const PATH_FALLBACK_BODY = "text-[var(--lesson-text-muted)] text-sm";

const PATH_CAROUSEL_INDEX = "text-[var(--lesson-text-muted)] text-xs tabular-nums";

const MOTION_SPRING_BUTTON = { type: "spring" as const, stiffness: 420, damping: 28 };

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
      <h2 className={PATH_UNIT_CARD_TITLE}>
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
                  width: progressWidthPercent(unit.completed_lessons, unit.lesson_count),
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

export function UnitCarousel({
  slides,
  selectedUnitId,
  onUnitChange,
  activeUnitId,
  currentLessonId,
  fallbackTitle,
  fallbackBody,
  sidePanel,
}: {
  slides: PathUnitSlide[];
  selectedUnitId: string | null;
  onUnitChange: (unitId: string) => void;
  activeUnitId: string | null;
  currentLessonId: string | null;
  fallbackTitle: string;
  fallbackBody: string;
  sidePanel?: ReactNode;
}) {
  /** Slide transition direction: derived from index delta when selection changes (any source). */
  const [direction, setDirection] = useState(0);
  const prevDisplayIndexRef = useRef<number | null>(null);

  const count = slides.length;
  const lastIndex = Math.max(count - 1, 0);
  const displayIndex = useMemo(() => {
    if (count === 0) return 0;
    const j = slides.findIndex((s) => s.unit.id === selectedUnitId);
    if (j >= 0) return j;
    return 0;
  }, [slides, selectedUnitId, count]);
  const slide = count > 0 ? slides[displayIndex] : undefined;

  useLayoutEffect(() => {
    const prev = prevDisplayIndexRef.current;
    if (prev !== null && prev !== displayIndex) {
      setDirection(displayIndex > prev ? 1 : -1);
    }
    prevDisplayIndexRef.current = displayIndex;
  }, [displayIndex]);

  const canGoUp = displayIndex > 0;
  const canGoDown = displayIndex < lastIndex;

  const goPrev = () => {
    if (!canGoUp || displayIndex <= 0) return;
    const prevSlide = slides[displayIndex - 1];
    if (!prevSlide) return;
    onUnitChange(prevSlide.unit.id);
  };

  const goNext = () => {
    if (!canGoDown || displayIndex >= lastIndex) return;
    const nextSlide = slides[displayIndex + 1];
    if (!nextSlide) return;
    onUnitChange(nextSlide.unit.id);
  };

  const roundNavClass =
    "flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-[var(--lesson-border)] bg-[var(--lesson-surface)] text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.08)] transition hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:border-[var(--lesson-border)] disabled:hover:bg-[var(--lesson-surface)]";

  if (count === 0 || slide === undefined) {
    if (sidePanel) {
      return (
        <div className="grid w-full min-w-0 grid-cols-1 items-start gap-6 md:grid-cols-2 md:gap-8">
          <section className={`w-full ${PATH_UNIT_SURFACE_CARD}`}>
            <div className="flex flex-col gap-1.5">
              <h2 className={PATH_UNIT_CARD_TITLE}>{fallbackTitle}</h2>
              <p className={PATH_FALLBACK_BODY}>{fallbackBody}</p>
            </div>
          </section>
          <div className="hidden min-h-0 min-w-0 md:block">{sidePanel}</div>
        </div>
      );
    }
    return (
      <section className={`w-full ${PATH_UNIT_SURFACE_CARD}`}>
        <div className="flex flex-col gap-1.5">
          <h2 className={PATH_UNIT_CARD_TITLE}>{fallbackTitle}</h2>
          <p className={PATH_FALLBACK_BODY}>{fallbackBody}</p>
        </div>
      </section>
    );
  }

  const carouselCard = (
    <div
      className={`relative min-h-[18.5rem] w-full min-w-0 overflow-hidden ${PATH_UNIT_SURFACE_CARD}`}
    >
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
          transition={MOTION_SPRING_BUTTON}
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
          transition={MOTION_SPRING_BUTTON}
          type="button"
          {...(canGoDown ? { whileTap: { scale: 0.92 } } : {})}
        >
          <ChevronDown aria-hidden="true" className="h-5 w-5" strokeWidth={2.25} />
        </motion.button>

        <p className={`order-4 ${PATH_CAROUSEL_INDEX} md:col-start-1 md:row-start-4`}>
          {displayIndex + 1} / {count}
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
        transition={MOTION_SPRING_BUTTON}
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
        transition={MOTION_SPRING_BUTTON}
        type="button"
        {...(canGoDown ? { whileTap: { scale: 0.92 } } : {})}
      >
        <ChevronDown aria-hidden="true" className="h-5 w-5" strokeWidth={2.25} />
      </motion.button>

      <p className={PATH_CAROUSEL_INDEX}>
        {displayIndex + 1} / {count}
      </p>
    </section>
  );
}
