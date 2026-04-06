import { useMutation } from "@tanstack/react-query";

import {
  authedRequestHeaders,
  nextItemApiV1LessonsLessonIdNextItemGet,
  requireResponseData,
  submitApiV1LessonsLessonIdSubmitPost,
} from "../../shared/api";
import type { LessonItemResponse, SubmitResponse } from "../../shared/api/generated/types.gen";

/** Load a lesson item by cursor (next-item API). Prefer this name for intent clarity at call sites. */
export function useLoadLessonItem(lessonId: string) {
  return useMutation({
    mutationFn: async (cursor: number) => {
      const result = await nextItemApiV1LessonsLessonIdNextItemGet({
        headers: authedRequestHeaders(),
        path: { lesson_id: lessonId },
        query: { cursor },
      });
      return requireResponseData(result.data as LessonItemResponse | undefined);
    },
  });
}

type CheckLessonAnswerPayload = { itemId: string; userAnswer: string };

type CompleteLessonPayload = {
  answers: Array<{ itemId: string; userAnswer: string }>;
};

async function submitLesson(
  lessonId: string,
  payload: CheckLessonAnswerPayload | CompleteLessonPayload,
): Promise<SubmitResponse> {
  const answers =
    "answers" in payload
      ? payload.answers.map((answer) => ({
          item_id: answer.itemId,
          user_answer: answer.userAnswer,
        }))
      : [
          {
            item_id: payload.itemId,
            user_answer: payload.userAnswer,
          },
        ];
  const result = await submitApiV1LessonsLessonIdSubmitPost({
    headers: authedRequestHeaders(),
    path: { lesson_id: lessonId },
    body: {
      answers,
    },
  });
  return requireResponseData(result.data as SubmitResponse | undefined);
}

/** Single-item answer check (same HTTP endpoint as completion, separate mutation for UI state). */
export function useCheckLessonAnswer(lessonId: string) {
  return useMutation({
    mutationFn: (payload: CheckLessonAnswerPayload) => submitLesson(lessonId, payload),
  });
}

/** Final lesson submission with all answers (same HTTP endpoint as check, separate mutation for UI state). */
export function useCompleteLesson(lessonId: string) {
  return useMutation({
    mutationFn: (payload: CompleteLessonPayload) => submitLesson(lessonId, payload),
  });
}
