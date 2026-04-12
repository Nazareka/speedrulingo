import { useParams } from "@tanstack/react-router";

import { LessonScreen } from "../features/lesson/lesson-screen";

export function LessonPage() {
  const { lessonId } = useParams({ from: "/lesson/$lessonId" });
  return <LessonScreen lessonId={lessonId} />;
}
