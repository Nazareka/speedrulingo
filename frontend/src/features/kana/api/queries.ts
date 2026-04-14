import { type QueryClient, queryOptions, useMutation, useQuery } from "@tanstack/react-query";

import {
  authedRequestHeaders,
  kanaContinueApiV1KanaContinuePost,
  kanaNextItemApiV1KanaLessonsLessonIdNextItemGet,
  kanaOverviewApiV1KanaOverviewGet,
  kanaSubmitApiV1KanaLessonsLessonIdSubmitPost,
  requireResponseData,
} from "../../../shared/api";
import type {
  KanaContinueResponse,
  KanaLessonItemResponse,
  KanaOverviewResponse,
  KanaSubmitResponse,
} from "../../../shared/api/generated/types.gen";

export const kanaKeys = {
  overview: ["kana", "overview"] as const,
  lesson: (lessonId: string) => ["kana", "lesson", lessonId] as const,
};

export function kanaOverviewQueryOptions() {
  return queryOptions({
    queryKey: kanaKeys.overview,
    queryFn: async ({ signal }) => {
      const result = await kanaOverviewApiV1KanaOverviewGet({
        headers: authedRequestHeaders(),
        signal,
      });
      return requireResponseData(
        result as { data: KanaOverviewResponse | undefined; response: Response },
      );
    },
    // Planned-lesson highlights (`is_next_lesson_new`) must match the server immediately; a long
    // stale window kept grey tiles until something else refetched (e.g. opening /kana/lesson/…).
    staleTime: 0,
    refetchOnMount: "always",
  });
}

export function useKanaOverviewQuery() {
  return useQuery(kanaOverviewQueryOptions());
}

export function useContinueKanaLearning() {
  return useMutation({
    mutationFn: async (): Promise<KanaContinueResponse> => {
      const result = await kanaContinueApiV1KanaContinuePost({
        headers: authedRequestHeaders(),
      });
      return requireResponseData(
        result as { data: KanaContinueResponse | undefined; response: Response },
      );
    },
  });
}

/** Fetches fresh overview into the cache (replaces invalidate + ensure for `staleTime: 0` queries). */
export function refreshKanaOverviewQuery(queryClient: QueryClient) {
  return queryClient.fetchQuery(kanaOverviewQueryOptions());
}

export async function loadKanaLessonItem(
  lessonId: string,
  cursor: number,
  signal?: AbortSignal,
): Promise<KanaLessonItemResponse> {
  const result = await kanaNextItemApiV1KanaLessonsLessonIdNextItemGet({
    headers: authedRequestHeaders(),
    path: { lesson_id: lessonId },
    query: { cursor },
    ...(signal ? { signal } : {}),
  });
  return requireResponseData(
    result as { data: KanaLessonItemResponse | undefined; response: Response },
  );
}

export function useLoadKanaLessonItem(lessonId: string) {
  return useMutation({
    mutationKey: kanaKeys.lesson(lessonId),
    mutationFn: async (cursor: number): Promise<KanaLessonItemResponse> =>
      loadKanaLessonItem(lessonId, cursor),
  });
}

export function useSubmitKanaLesson(lessonId: string) {
  return useMutation({
    mutationFn: async (
      answers: Array<{ itemId: string; optionId: string }>,
    ): Promise<KanaSubmitResponse> => {
      const result = await kanaSubmitApiV1KanaLessonsLessonIdSubmitPost({
        headers: authedRequestHeaders(),
        path: { lesson_id: lessonId },
        body: {
          answers: answers.map((answer) => ({
            item_id: answer.itemId,
            option_id: answer.optionId,
          })),
        },
      });
      return requireResponseData(
        result as { data: KanaSubmitResponse | undefined; response: Response },
      );
    },
  });
}
