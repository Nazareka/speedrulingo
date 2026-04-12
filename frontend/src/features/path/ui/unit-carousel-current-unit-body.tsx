import type { PathUnitSlide } from "../../../entities/path/model";
import { progressWidthPercent } from "../../../entities/path/unit-lessons";
import { LessonCircleChain } from "./lesson-circle-chain";
import { ChainSpine } from "./unit-carousel-spine";

export function CurrentUnitBody({
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
