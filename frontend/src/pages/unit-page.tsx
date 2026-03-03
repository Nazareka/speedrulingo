import { Link, useParams } from "@tanstack/react-router";

import { useUnitDetailQuery } from "../features/units/queries";

export function UnitPage() {
  const params = useParams({ from: "/unit/$unitId" });
  const unitQuery = useUnitDetailQuery(params.unitId);

  if (unitQuery.isLoading) {
    return <div className="h-64 animate-pulse rounded-[1.75rem] bg-stone-200" />;
  }

  if (!unitQuery.data) {
    return (
      <div className="rounded-[1.75rem] border border-stone-200 bg-white px-6 py-8 text-stone-700">
        Unit not found.
      </div>
    );
  }

  const unit = unitQuery.data;

  return (
    <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
      <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
        <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">
          {unit.section_title}
        </p>
        <h2 className="mt-3 font-semibold text-3xl text-stone-900">{unit.title}</h2>
        <p className="mt-2 text-sm text-stone-500 leading-6">{unit.description}</p>
        <div className="mt-6 grid gap-3">
          {unit.lessons.map((lesson) => (
            <div
              className={`flex items-center justify-between rounded-[1.25rem] border px-4 py-4 ${
                lesson.is_locked
                  ? "border-stone-200 bg-stone-100 text-stone-500"
                  : "border-stone-200 bg-stone-50"
              }`}
              key={lesson.id}
            >
              <div>
                <p className="font-medium text-sm text-stone-900">
                  {lesson.kind === "exam" ? "Exam" : `Lesson ${lesson.order_index}`}
                </p>
                <p className="mt-1 text-stone-500 text-xs">
                  {lesson.state.replace("_", " ")}
                  {lesson.attempts_used !== undefined && lesson.attempts_used !== null
                    ? ` · attempts used: ${lesson.attempts_used}`
                    : ""}
                </p>
              </div>
              {lesson.is_locked ? (
                <span className="rounded-full border border-stone-300 px-3 py-1 text-xs">
                  Locked
                </span>
              ) : (
                <Link
                  className="rounded-full bg-stone-900 px-4 py-2 text-sm text-white transition hover:bg-stone-700"
                  params={{ lessonId: lesson.id }}
                  to="/lesson/$lessonId"
                >
                  {lesson.state === "completed" ? "Retry" : "Start"}
                </Link>
              )}
            </div>
          ))}
        </div>
      </section>
      <section className="grid gap-6">
        <article className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
          <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">Guide</p>
          <div className="mt-4 space-y-3">
            <div>
              <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Pattern tags</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {unit.pattern_tags.map((tag) => (
                  <span
                    className="rounded-full bg-amber-100 px-3 py-1 text-amber-800 text-xs"
                    key={tag}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="text-stone-500 text-xs uppercase tracking-[0.25em]">Theme tags</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {unit.theme_tags.map((tag) => (
                  <span
                    className="rounded-full bg-stone-100 px-3 py-1 text-stone-700 text-xs"
                    key={tag}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-6 rounded-[1.5rem] bg-stone-50 p-5 text-sm text-stone-700 leading-7">
            {unit.article_md ? (
              <div className="whitespace-pre-wrap">{unit.article_md}</div>
            ) : (
              <p>Guide not available yet.</p>
            )}
          </div>
        </article>
        <article className="rounded-[1.75rem] border border-stone-200 bg-white p-6">
          <p className="font-mono text-[11px] text-stone-500 uppercase tracking-[0.35em]">
            Sentence samples
          </p>
          <div className="mt-4 grid gap-3">
            {unit.sentence_samples.map((sentence) => (
              <div
                className="rounded-[1.25rem] border border-stone-200 bg-stone-50 px-4 py-4"
                key={sentence.id}
              >
                <p className="text-base text-stone-900">{sentence.ja_text}</p>
                <p className="mt-1 text-sm text-stone-500">{sentence.en_text}</p>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
