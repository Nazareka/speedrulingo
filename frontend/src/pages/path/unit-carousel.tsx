import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { LessonCircleChain } from "./lesson-circle-chain";
import { progressWidthPercent } from "./lesson-derive";
import type { PathUnitSlide } from "./model";

function unitCarouselLabel(slide: PathUnitSlide): string {
  const t = slide.unit.title.trim();
  return t.length > 0 ? t : `${slide.sectionTitle} Unit ${slide.unit.unit_order_index}`;
}

/** Shared surface card shell (empty state + carousel viewport). */
const PATH_UNIT_SURFACE_CARD =
  "rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-3 shadow-[0_6px_18px_rgba(37,99,235,0.05)]";

/** Unit carousel card title (fallback empty state + active slide). */
const PATH_UNIT_CARD_TITLE =
  "font-semibold text-[var(--lesson-text)] text-lg leading-snug tracking-[-0.02em] md:text-xl";
const PATH_FALLBACK_BODY = "text-[var(--lesson-text-muted)] text-sm";

const PATH_CAROUSEL_INDEX = "text-[var(--lesson-text-muted)] text-xs tabular-nums";

const WIDE_UNIT_NAV_BASE =
  "w-full min-w-0 rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-3 py-2.5 text-left font-medium text-sm text-[var(--lesson-text)] shadow-[0_2px_8px_rgba(37,99,235,0.06)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.35)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-[var(--lesson-border)] disabled:hover:bg-[var(--lesson-surface)]";

const WIDE_UNIT_NAV_INTERACTIVE =
  "hover:border-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)] active:scale-[0.99]";

const WIDE_UNIT_NAV_CURRENT =
  "w-full min-w-0 rounded-xl border-2 border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] px-3 py-2.5 text-left font-semibold text-sm text-[var(--lesson-text)] shadow-[0_2px_10px_rgba(37,99,235,0.12)]";

/** Short vertical spine connecting prev and current buttons. */
const UNIT_NAV_DASHED_SHORT = "h-4 w-[3px] shrink-0 rounded-full bg-[var(--lesson-border-soft)]";

/** Vertical segment matching lesson connectors — links unit blocks into one path. */
const CHAIN_SPINE =
  "h-[14px] min-h-[14px] w-[3px] shrink-0 rounded-full bg-[var(--lesson-border-soft)]";

const PATH_UNIT_SWAP_EASE = [0.22, 1, 0.36, 1] as const;
const PATH_UNIT_CHAIN_DURATION = 0.62;
const CHAIN_BRIDGE_HEIGHT = 14;
const CHAIN_ANIMATION_MS = 700;
const CHAIN_NODE_SIZE = 48;
const CHAIN_MIN_CONNECTOR = 14;
const CHAIN_END_SPINES = 28;

function ChainSpine() {
  return (
    <div aria-hidden="true" className="flex justify-center py-0">
      <div className={CHAIN_SPINE} />
    </div>
  );
}

type ChainTransitionState = {
  id: number;
  from: PathUnitSlide;
  to: PathUnitSlide;
  direction: number;
};

function CurrentUnitBody({
  slide,
  currentLessonId,
  isApiActiveUnit,
  lessonChainHeight,
}: {
  slide: PathUnitSlide;
  currentLessonId: string | null;
  isApiActiveUnit: boolean;
  lessonChainHeight: number;
}) {
  const { unit } = slide;

  const middleContent = (() => {
    if (unit.is_locked) {
      return unit.lessons.length > 0 ? (
        <LessonCircleChain
          currentLessonId={currentLessonId}
          isApiActiveUnit={isApiActiveUnit}
          lessons={unit.lessons}
          orientation="vertical"
          showLessonsLabel={false}
          unitLocked
          verticalHeight={lessonChainHeight}
        />
      ) : null;
    }
    if (unit.lessons.length > 0) {
      return (
        <LessonCircleChain
          currentLessonId={currentLessonId}
          isApiActiveUnit={isApiActiveUnit}
          lessons={unit.lessons}
          orientation="vertical"
          showLessonsLabel={false}
          unitLocked={false}
          verticalHeight={lessonChainHeight}
        />
      );
    }
    if (!unit.is_completed) {
      return (
        <div className="flex w-full flex-col items-center py-1">
          <div className="h-1.5 w-36 shrink-0 overflow-hidden rounded-full bg-[var(--lesson-border-soft)]">
            <div
              className="h-full rounded-full bg-[var(--lesson-accent)]"
              style={{
                width: progressWidthPercent(unit.completed_lessons, unit.lesson_count),
              }}
            />
          </div>
        </div>
      );
    }
    return null;
  })();

  if (middleContent === null) {
    return <ChainSpine />;
  }

  return (
    <>
      <ChainSpine />
      {middleContent}
      <ChainSpine />
    </>
  );
}

function NavButton({
  label,
  ariaLabel,
  disabled,
  onClick,
}: {
  label: string;
  ariaLabel: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={ariaLabel}
      className={`relative z-10 ${WIDE_UNIT_NAV_BASE} ${disabled ? "" : WIDE_UNIT_NAV_INTERACTIVE}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function ChainSlideBody({
  slide,
  currentLessonId,
  activeUnitId,
  lessonChainHeight,
}: {
  slide: PathUnitSlide;
  currentLessonId: string | null;
  activeUnitId: string | null;
  lessonChainHeight: number;
}) {
  return (
    <CurrentUnitBody
      currentLessonId={currentLessonId}
      isApiActiveUnit={slide.unit.id === activeUnitId}
      lessonChainHeight={lessonChainHeight}
      slide={slide}
    />
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
  const [chainTransition, setChainTransition] = useState<ChainTransitionState | null>(null);
  const prevDisplayIndexRef = useRef<number | null>(null);
  const transitionIdRef = useRef(0);

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
      const nextDirection = displayIndex > prev ? 1 : -1;
      const from = slides[prev];
      const to = slides[displayIndex];
      if (from && to) {
        transitionIdRef.current += 1;
        setChainTransition({
          id: transitionIdRef.current,
          from,
          to,
          direction: nextDirection,
        });
      }
    }
    prevDisplayIndexRef.current = displayIndex;
  }, [displayIndex, slides]);

  useEffect(() => {
    if (chainTransition === null) return;
    const timer = window.setTimeout(() => {
      setChainTransition((current) => (current?.id === chainTransition.id ? null : current));
    }, CHAIN_ANIMATION_MS);
    return () => window.clearTimeout(timer);
  }, [chainTransition]);

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

  const prevSlide = displayIndex > 0 ? slides[displayIndex - 1] : undefined;
  const nextSlideNav = displayIndex < lastIndex ? slides[displayIndex + 1] : undefined;

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

  const prevLabel = prevSlide ? unitCarouselLabel(prevSlide) : "No previous unit";
  const nextLabel = nextSlideNav ? unitCarouselLabel(nextSlideNav) : "No next unit";
  const maxLessonCount = slides.reduce((max, item) => Math.max(max, item.unit.lessons.length), 0);
  const normalizedLessonChainHeight =
    maxLessonCount > 0
      ? maxLessonCount * CHAIN_NODE_SIZE + Math.max(maxLessonCount - 1, 0) * CHAIN_MIN_CONNECTOR
      : 0;
  const chainViewportHeight = Math.max(normalizedLessonChainHeight + CHAIN_END_SPINES, 120);

  const chainStripHeight =
    chainTransition === null ? chainViewportHeight : chainViewportHeight * 2 + CHAIN_BRIDGE_HEIGHT;

  const chainStartY =
    chainTransition === null
      ? 0
      : chainTransition.direction > 0
        ? 0
        : -(chainViewportHeight + CHAIN_BRIDGE_HEIGHT);

  const chainEndY =
    chainTransition === null
      ? 0
      : chainTransition.direction > 0
        ? -(chainViewportHeight + CHAIN_BRIDGE_HEIGHT)
        : 0;

  const carouselCard = (
    <div className={`relative w-full min-w-0 overflow-hidden ${PATH_UNIT_SURFACE_CARD}`}>
      <div className="flex w-full min-w-0 flex-col items-stretch gap-0">
        <NavButton
          ariaLabel={prevSlide ? `Go to previous unit: ${prevLabel}` : "No previous unit"}
          disabled={!prevSlide}
          label={prevLabel}
          onClick={goPrev}
        />

        <div aria-hidden="true" className="-my-px flex h-4 w-full justify-center">
          {prevSlide ? <div className={UNIT_NAV_DASHED_SHORT} /> : null}
        </div>

        <div aria-current="page" className={`relative z-10 ${WIDE_UNIT_NAV_CURRENT}`} role="status">
          {unitCarouselLabel(slide)}
        </div>

        <div
          className="relative z-0 w-full overflow-hidden"
          style={{ height: `${chainViewportHeight}px` }}
        >
          <motion.div
            animate={{ y: chainEndY }}
            className="absolute inset-x-0 top-0"
            initial={{ y: chainStartY }}
            key={
              chainTransition === null
                ? `chain-static-${slide.unit.id}`
                : `chain-slide-${chainTransition.id}`
            }
            transition={{ duration: PATH_UNIT_CHAIN_DURATION, ease: PATH_UNIT_SWAP_EASE }}
            style={{ height: `${chainStripHeight}px` }}
          >
            {chainTransition === null ? (
              <ChainSlideBody
                activeUnitId={activeUnitId}
                currentLessonId={currentLessonId}
                lessonChainHeight={normalizedLessonChainHeight}
                slide={slide}
              />
            ) : chainTransition.direction > 0 ? (
              <>
                <ChainSlideBody
                  activeUnitId={activeUnitId}
                  currentLessonId={currentLessonId}
                  lessonChainHeight={normalizedLessonChainHeight}
                  slide={chainTransition.from}
                />
                <ChainSpine />
                <ChainSlideBody
                  activeUnitId={activeUnitId}
                  currentLessonId={currentLessonId}
                  lessonChainHeight={normalizedLessonChainHeight}
                  slide={chainTransition.to}
                />
              </>
            ) : (
              <>
                <ChainSlideBody
                  activeUnitId={activeUnitId}
                  currentLessonId={currentLessonId}
                  lessonChainHeight={normalizedLessonChainHeight}
                  slide={chainTransition.to}
                />
                <ChainSpine />
                <ChainSlideBody
                  activeUnitId={activeUnitId}
                  currentLessonId={currentLessonId}
                  lessonChainHeight={normalizedLessonChainHeight}
                  slide={chainTransition.from}
                />
              </>
            )}
          </motion.div>
        </div>

        <NavButton
          ariaLabel={nextSlideNav ? `Go to next unit: ${nextLabel}` : "No next unit"}
          disabled={!nextSlideNav}
          label={nextLabel}
          onClick={goNext}
        />
      </div>
    </div>
  );

  if (sidePanel) {
    return (
      <section className="flex w-full flex-col items-stretch gap-2 md:grid md:grid-cols-2 md:items-start md:gap-x-8 md:gap-y-2">
        <div className="order-1 w-full min-w-0 md:col-start-1 md:row-start-1">{carouselCard}</div>

        <div className="order-5 hidden min-h-0 w-full min-w-0 md:order-none md:col-start-2 md:row-span-2 md:row-start-1 md:block md:self-start">
          {sidePanel}
        </div>

        <p className={`order-2 ${PATH_CAROUSEL_INDEX} md:col-start-1 md:row-start-2`}>
          {displayIndex + 1} / {count}
        </p>
      </section>
    );
  }

  return (
    <section className="flex w-full flex-col items-stretch gap-2">
      {carouselCard}
      <p className={PATH_CAROUSEL_INDEX}>
        {displayIndex + 1} / {count}
      </p>
    </section>
  );
}
