import type { UnitDetail } from "../../shared/api/generated/types.gen";

type UnitGuideFields = Pick<UnitDetail, "article_md" | "pattern_tags" | "theme_tags">;

export function UnitGuideCard({ unit }: { unit: UnitGuideFields }) {
  return (
    <article className="rounded-[1.75rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-6 shadow-[0_6px_18px_rgba(37,99,235,0.05)]">
      <p className="font-mono text-[11px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
        Guide
      </p>
      <div className="mt-4 space-y-3">
        <div>
          <p className="text-[var(--lesson-text-muted)] text-xs uppercase tracking-[0.25em]">
            Pattern tags
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {unit.pattern_tags.map((tag) => (
              <span
                className="rounded-full bg-amber-100 px-3 py-1 font-medium text-amber-800 text-xs uppercase"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[var(--lesson-text-muted)] text-xs uppercase tracking-[0.25em]">
            Theme tags
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {unit.theme_tags.map((tag) => (
              <span
                className="rounded-full bg-[var(--lesson-border-soft)] px-3 py-1 font-medium text-[var(--lesson-text-muted)] text-xs uppercase"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-6 rounded-[1.5rem] bg-[var(--lesson-surface-muted)] p-5 text-[var(--lesson-text)] text-sm leading-7">
        {unit.article_md ? (
          <div className="whitespace-pre-wrap">{unit.article_md}</div>
        ) : (
          <p>Guide not available yet.</p>
        )}
      </div>
    </article>
  );
}
