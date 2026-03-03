import { useMemo, useState } from "react";

import { useKanjiDetailQuery, useKanjiLessonsQuery } from "../features/kanji/queries";

export function KanjiPage() {
  const lessonsQuery = useKanjiLessonsQuery();
  const [selectedKanji, setSelectedKanji] = useState<string | null>(null);
  const detailQuery = useKanjiDetailQuery(selectedKanji);

  const allKanji = useMemo(() => {
    return lessonsQuery.data?.lessons.flatMap((lesson) => lesson.kanji_chars) ?? [];
  }, [lessonsQuery.data]);

  return (
    <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
      <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
        <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">
          Kanji lessons
        </p>
        <div className="mt-4 grid gap-3">
          {lessonsQuery.data?.lessons.map((lesson) => (
            <div
              className="rounded-[1.25rem] border border-stone-200 bg-stone-50 px-4 py-4"
              key={lesson.lesson_id}
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-sm text-stone-900">
                    Unit {lesson.unit_order_index} · Lesson {lesson.lesson_order_index}
                  </p>
                  <p className="mt-1 text-stone-500 text-xs">{lesson.state.replace("_", " ")}</p>
                </div>
                <span className="rounded-full bg-stone-200 px-3 py-1 text-stone-700 text-xs">
                  {lesson.kanji_chars.length} kanji
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {lesson.kanji_chars.map((kanji) => (
                  <button
                    className={`grid size-12 place-items-center rounded-2xl border text-lg transition ${
                      selectedKanji === kanji
                        ? "border-stone-900 bg-stone-900 text-white"
                        : "border-stone-300 bg-white text-stone-900 hover:bg-stone-100"
                    }`}
                    key={`${lesson.lesson_id}-${kanji}`}
                    onClick={() => {
                      setSelectedKanji(kanji);
                    }}
                    type="button"
                  >
                    {kanji}
                  </button>
                ))}
              </div>
            </div>
          )) ?? <p className="text-sm text-stone-600">No kanji introductions are available yet.</p>}
        </div>
      </section>
      <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
        <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">
          Kanji details
        </p>
        {!selectedKanji ? (
          <div className="mt-8">
            <p className="text-sm text-stone-600">
              Pick a kanji from the left. Current course inventory: {allKanji.join(" ")}
            </p>
          </div>
        ) : detailQuery.isLoading ? (
          <div className="mt-8 h-48 animate-pulse rounded-[1.5rem] bg-stone-200" />
        ) : detailQuery.data ? (
          <div className="mt-8">
            <div className="flex items-end gap-4">
              <div className="grid size-24 place-items-center rounded-[1.75rem] bg-stone-900 text-5xl text-white">
                {detailQuery.data.kanji_char}
              </div>
              <div>
                <p className="text-sm text-stone-500">Primary meaning</p>
                <h2 className="font-semibold text-3xl text-stone-900">
                  {detailQuery.data.primary_meaning ?? "Unavailable"}
                </h2>
              </div>
            </div>
            <div className="mt-8 grid gap-3">
              {detailQuery.data.usages.map((usage) => (
                <div
                  className="rounded-[1.25rem] border border-stone-200 bg-stone-50 px-4 py-4"
                  key={`${usage.lesson_id}-${usage.example_word_ja}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-sm text-stone-900">
                      Unit {usage.unit_order_index} · Lesson {usage.lesson_order_index}
                    </p>
                    <span
                      className={`rounded-full px-3 py-1 text-xs ${
                        usage.is_learned
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-stone-200 text-stone-600"
                      }`}
                    >
                      {usage.is_learned ? "Learned" : "Upcoming"}
                    </span>
                  </div>
                  <p className="mt-3 text-lg text-stone-900">{usage.example_word_ja}</p>
                  <p className="mt-1 text-sm text-stone-500">
                    {usage.example_reading ?? "Reading unavailable"} · {usage.meaning_en}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="mt-8 text-sm text-stone-600">Kanji details are unavailable.</p>
        )}
      </section>
    </div>
  );
}
