import type { ReactNode } from "react";

type LessonSprintCompleteSummaryProps = {
  accentLabel: string;
  correctCount: number;
  mistakeCount: number;
  completionProgressState: string | null;
  /** Optional block between the stats paragraph and the primary action (e.g. stat cards). */
  middle?: ReactNode;
  footer: ReactNode;
};

/** Shared headline + stats copy for lesson sprint completion (path + kana). */
export function LessonSprintCompleteSummary(props: LessonSprintCompleteSummaryProps) {
  const { accentLabel, correctCount, mistakeCount, completionProgressState, middle, footer } =
    props;

  return (
    <>
      <p className="font-medium text-[var(--lesson-accent)] text-sm">{accentLabel}</p>

      <h1 className="mt-3 font-semibold text-4xl text-[var(--lesson-text)] tracking-[-0.03em] md:text-5xl">
        {mistakeCount === 0 ? "Clean finish." : "Every item solved."}
      </h1>

      <p className="mt-4 max-w-2xl text-[var(--lesson-text-muted)] text-base leading-7">
        Correct checks: {correctCount}. Review fixes: {mistakeCount}. Progress state:{" "}
        {(completionProgressState ?? "completed").replaceAll("_", " ")}.
      </p>

      {middle ? <div className="mt-8">{middle}</div> : null}

      <div className="mt-8">{footer}</div>
    </>
  );
}
