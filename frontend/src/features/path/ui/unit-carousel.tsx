import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { PathUnitSlide } from "../../../entities/path/model";
import {
  CHAIN_ANIMATION_MS,
  CHAIN_BRIDGE_HEIGHT,
  CHAIN_END_SPINES,
  CHAIN_MIN_CONNECTOR,
  CHAIN_NODE_SIZE,
  type ChainTransitionState,
  PATH_CAROUSEL_INDEX,
  PATH_FALLBACK_BODY,
  PATH_UNIT_CARD_TITLE,
  PATH_UNIT_CHAIN_DURATION,
  PATH_UNIT_SURFACE_CARD,
  PATH_UNIT_SWAP_EASE,
  UNIT_NAV_DASHED_SHORT,
  unitCarouselLabel,
  WIDE_UNIT_NAV_CURRENT,
} from "./unit-carousel.constants";
import { ChainSlideBody } from "./unit-carousel-chain-slide-body";
import { NavButton } from "./unit-carousel-nav-button";
import { ChainSpine } from "./unit-carousel-spine";

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
