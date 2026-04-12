import type { PathUnitSlide } from "../../../entities/path/model";
import { CurrentUnitBody } from "./unit-carousel-current-unit-body";

export function ChainSlideBody({
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
