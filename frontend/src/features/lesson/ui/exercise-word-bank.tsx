import type { FeedbackState } from "../../../entities/lesson/session-types";
import { LESSON_ANSWER_CONTROL } from "../lib/shortcuts";
import type { TileInstance } from "../model/tile-helpers";
import { optionTypographyClass } from "../model/typography";

type WordBankExerciseProps = {
  addTile: (tile: string) => void;
  availableTileInstances: Array<TileInstance>;
  feedback: FeedbackState | null;
  removeTileAt: (index: number) => void;
  selectedTileInstances: Array<TileInstance>;
  selectedTiles: Array<string>;
};

export function WordBankExercise(props: WordBankExerciseProps) {
  const {
    addTile,
    availableTileInstances,
    feedback,
    removeTileAt,
    selectedTileInstances,
    selectedTiles,
  } = props;

  return (
    <div className="grid gap-4">
      <section className="rounded-2xl border border-[var(--lesson-border)] bg-[color:var(--lesson-surface-muted)]/78 p-4">
        <div className="rounded-xl bg-[var(--lesson-surface)] p-4">
          {selectedTiles.length === 0 ? (
            <div className="flex min-h-24 items-center rounded-lg bg-[var(--lesson-surface-subtle)] px-4 py-3">
              <span className="text-[var(--lesson-text-faint)] text-sm">
                Tap the word bank to build the sentence.
              </span>
            </div>
          ) : (
            <div className="flex min-h-24 flex-wrap content-start gap-2">
              {selectedTileInstances.map((tileInstance, index) => (
                <button
                  className={`rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-4 py-2.5 font-medium text-[var(--lesson-text)] transition hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface-muted)] active:scale-[0.99] ${optionTypographyClass(
                    tileInstance.text,
                  )} ${feedback ? "opacity-70" : ""}`}
                  disabled={feedback !== null}
                  key={tileInstance.id}
                  onClick={() => {
                    if (feedback) {
                      return;
                    }
                    removeTileAt(index);
                  }}
                  type="button"
                >
                  {tileInstance.text}
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--lesson-border)] bg-[color:var(--lesson-surface-muted)]/78 p-4">
        <div className="flex min-h-24 flex-wrap content-start gap-2">
          {availableTileInstances.map((tileInstance) => (
            <button
              {...{ [LESSON_ANSWER_CONTROL]: "" }}
              className={`rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-4 py-2.5 font-medium text-[var(--lesson-text)] transition hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface-muted)] ${optionTypographyClass(
                tileInstance.text,
              )} ${feedback ? "opacity-70" : ""}`}
              disabled={feedback !== null}
              key={tileInstance.id}
              onClick={() => {
                if (feedback) {
                  return;
                }
                addTile(tileInstance.text);
              }}
              type="button"
            >
              {tileInstance.text}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
