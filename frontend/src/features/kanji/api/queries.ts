import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  authedRequestHeaders,
  kanjiDetailApiV1KanjiKanjiCharGet,
  kanjiLessonsApiV1KanjiLessonsGet,
  requireResponseData,
} from "../../../shared/api";
import type {
  KanjiDetailResponse,
  KanjiLessonsResponse,
} from "../../../shared/api/generated/types.gen";

const kanjiKeys = {
  lessons: ["kanji", "lessons"] as const,
  detail: (kanjiChar: string) => ["kanji", kanjiChar] as const,
};

export function kanjiLessonsQueryOptions() {
  return queryOptions({
    queryKey: kanjiKeys.lessons,
    queryFn: async ({ signal }) => {
      const result = await kanjiLessonsApiV1KanjiLessonsGet({
        headers: authedRequestHeaders(),
        signal,
      });
      return requireResponseData(
        result as { data: KanjiLessonsResponse | undefined; response: Response },
      );
    },
    staleTime: 30_000,
  });
}

function kanjiDetailQueryOptions(kanjiChar: string | null) {
  return queryOptions({
    queryKey: kanjiKeys.detail(kanjiChar ?? "none"),
    queryFn: async ({ signal }) => {
      if (!kanjiChar) {
        throw new Error("Missing kanji");
      }
      const result = await kanjiDetailApiV1KanjiKanjiCharGet({
        headers: authedRequestHeaders(),
        path: { kanji_char: kanjiChar },
        signal,
      });
      return requireResponseData(
        result as { data: KanjiDetailResponse | undefined; response: Response },
      );
    },
    enabled: kanjiChar !== null,
    staleTime: 30_000,
  });
}

export function useKanjiLessonsQuery() {
  return useQuery(kanjiLessonsQueryOptions());
}

export function useKanjiDetailQuery(kanjiChar: string | null) {
  return useQuery(kanjiDetailQueryOptions(kanjiChar));
}
