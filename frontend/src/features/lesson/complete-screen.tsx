import { LessonSprintCompleteSummary } from "../../shared/lesson/sprint-complete-summary";
import { PRIMARY_BUTTON_CLASS } from "../../shared/lesson/ui-constants";

type LessonCompleteScreenProps = {
  completionProgressState: string | null;
  correctCount: number;
  mistakeCount: number;
  onBackToPath: () => void;
};

export function LessonCompleteScreen(props: LessonCompleteScreenProps) {
  const { completionProgressState, correctCount, mistakeCount, onBackToPath } = props;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 md:px-6 md:py-10">
      <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.05)] md:px-10 md:py-10">
        <LessonSprintCompleteSummary
          accentLabel="Speedrulingo sprint complete"
          completionProgressState={completionProgressState}
          correctCount={correctCount}
          footer={
            <button className={PRIMARY_BUTTON_CLASS} onClick={onBackToPath} type="button">
              Back to path
            </button>
          }
          middle={
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-5">
                <p className="text-[var(--lesson-text-soft)] text-sm">Cleared</p>
                <p className="mt-2 font-semibold text-4xl text-[var(--lesson-text)] tracking-[-0.03em]">
                  {correctCount}
                </p>
              </div>

              <div className="rounded-2xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-5">
                <p className="text-[var(--lesson-text-soft)] text-sm">Mistakes fixed</p>
                <p className="mt-2 font-semibold text-4xl text-[var(--lesson-text)] tracking-[-0.03em]">
                  {mistakeCount}
                </p>
              </div>
            </div>
          }
          mistakeCount={mistakeCount}
        />
      </section>
    </div>
  );
}
