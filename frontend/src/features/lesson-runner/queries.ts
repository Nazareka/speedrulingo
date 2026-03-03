import { useMutation } from "@tanstack/react-query";

import {
  explainTokenRouteApiV1ExplainTokenPost,
  nextItemApiV1LessonsLessonIdNextItemGet,
  submitApiV1LessonsLessonIdSubmitPost,
} from "../../shared/api";
import type {
  ExplainResponse,
  LessonItemResponse,
  SubmitResponse,
} from "../../shared/api/generated/types.gen";
import { buildAuthedHeaders } from "../auth/mutations";

export function useNextItemMutation(lessonId: string) {
  return useMutation({
    mutationFn: async (cursor: number) => {
      const result = await nextItemApiV1LessonsLessonIdNextItemGet({
        headers: buildAuthedHeaders(),
        path: { lesson_id: lessonId },
        query: { cursor },
      });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as LessonItemResponse;
    },
  });
}

export function useSubmitLessonMutation(lessonId: string) {
  return useMutation({
    mutationFn: async (
      payload:
        | { itemId: string; userAnswer: string }
        | { answers: Array<{ itemId: string; userAnswer: string }> },
    ) => {
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
        headers: buildAuthedHeaders(),
        path: { lesson_id: lessonId },
        body: {
          answers,
        },
      });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as SubmitResponse;
    },
  });
}

export function useExplainTokenMutation() {
  return useMutation({
    mutationFn: async (payload: { sentenceId: string; tokenSurface: string }) => {
      const result = await explainTokenRouteApiV1ExplainTokenPost({
        headers: buildAuthedHeaders(),
        body: {
          sentence_id: payload.sentenceId,
          token_surface: payload.tokenSurface,
        },
      });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as ExplainResponse;
    },
  });
}
