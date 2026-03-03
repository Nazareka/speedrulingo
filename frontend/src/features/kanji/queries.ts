import { useQuery } from "@tanstack/react-query";

import {
  kanjiDetailApiV1KanjiKanjiCharGet,
  kanjiLessonsApiV1KanjiLessonsGet,
} from "../../shared/api";
import type {
  KanjiDetailResponse,
  KanjiLessonsResponse,
} from "../../shared/api/generated/types.gen";
import { buildAuthedHeaders } from "../auth/mutations";

export const kanjiKeys = {
  lessons: ["kanji", "lessons"] as const,
  detail: (kanjiChar: string) => ["kanji", kanjiChar] as const,
};

export function useKanjiLessonsQuery() {
  return useQuery({
    queryKey: kanjiKeys.lessons,
    queryFn: async () => {
      const result = await kanjiLessonsApiV1KanjiLessonsGet({ headers: buildAuthedHeaders() });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as KanjiLessonsResponse;
    },
    staleTime: 30_000,
  });
}

export function useKanjiDetailQuery(kanjiChar: string | null) {
  return useQuery({
    queryKey: kanjiKeys.detail(kanjiChar ?? "none"),
    queryFn: async () => {
      if (!kanjiChar) {
        throw new Error("Missing kanji");
      }
      const result = await kanjiDetailApiV1KanjiKanjiCharGet({
        headers: buildAuthedHeaders(),
        path: { kanji_char: kanjiChar },
      });
      if (result.data === undefined) {
        throw new Error("API response was empty.");
      }
      return result.data as unknown as KanjiDetailResponse;
    },
    enabled: kanjiChar !== null,
    staleTime: 30_000,
  });
}
