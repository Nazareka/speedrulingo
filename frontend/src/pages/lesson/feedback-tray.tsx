import type { FeedbackState } from "./session-types";
import { optionTypographyClass } from "./typography";
import { PRIMARY_BUTTON_CLASS } from "./ui-constants";

type LessonFeedbackTrayProps = {
  feedback: FeedbackState;
  onContinue: () => void;
  continuePending?: boolean;
  continueError?: string | null;
};

export function LessonFeedbackTray(props: LessonFeedbackTrayProps) {
  const { feedback, onContinue, continuePending = false, continueError = null } = props;

  const trayTone = feedback.isCorrect
    ? "border-[var(--lesson-success-border)] bg-[var(--lesson-success-bg)]"
    : "border-[var(--lesson-error-border)] bg-[color:var(--lesson-error-bg)]";

  return (
    <div className={`rounded-[1.15rem] border px-5 py-4 ${trayTone}`}>
      <div className="flex flex-col gap-3">
        {continueError ? (
          <p className="text-[var(--lesson-error-accent)] text-sm">{continueError}</p>
        ) : null}

        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-white text-xs ${
                  feedback.isCorrect
                    ? "bg-[var(--lesson-accent)]"
                    : "bg-[var(--lesson-error-accent)]"
                }`}
              >
                {feedback.isCorrect ? "✓" : "!"}
              </span>

              <p className="font-semibold text-[1.1rem] text-[var(--lesson-text)] tracking-[-0.02em]">
                {feedback.isCorrect ? "Correct" : "Incorrect"}
              </p>
            </div>

            {feedback.isCorrect ? (
              <p className="mt-1 text-[var(--lesson-text-muted)] text-sm leading-6">
                Nice. Keep going.
              </p>
            ) : null}

            {!feedback.isCorrect ? (
              <div className="mt-2">
                <p className="text-[var(--lesson-text-soft)] text-sm">Correct answer:</p>
                <p
                  className={`mt-1 font-semibold text-[var(--lesson-text)] tracking-[-0.02em] ${optionTypographyClass(
                    feedback.expectedAnswer,
                  )}`}
                >
                  {feedback.expectedAnswer}
                </p>
              </div>
            ) : null}
          </div>

          <button
            className={`shrink-0 ${PRIMARY_BUTTON_CLASS} disabled:cursor-not-allowed disabled:opacity-70`}
            disabled={continuePending}
            onClick={onContinue}
            type="button"
          >
            {continuePending ? "Loading…" : "Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
