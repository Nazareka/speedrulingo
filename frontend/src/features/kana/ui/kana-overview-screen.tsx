import { LoaderCircle, Sparkles } from "lucide-react";

import { PRIMARY_BUTTON_CLASS } from "../../../shared/ui/tokens/button-classes";
import { useKanaOverviewPage } from "../model/use-kana-overview-page";

/** Kana inventory + continue CTA; route page only mounts this screen. */
export function KanaOverviewScreen() {
  const {
    overviewQuery,
    continueMutation,
    playbackError,
    playAudio,
    handleContinue,
    masteredPercent,
    groupRows,
    characterProgressPercent,
    isKanaOverviewTileTappable,
    kanaOverviewTileClassName,
  } = useKanaOverviewPage();

  if (overviewQuery.isLoading) {
    return (
      <div className="px-4 py-8 md:px-6 md:py-10">
        <div className="rounded-[1.75rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-8">
          <p className="text-[var(--lesson-text-soft)] text-sm">Loading kana inventory...</p>
        </div>
      </div>
    );
  }

  if (overviewQuery.error || !overviewQuery.data) {
    return (
      <div className="px-4 py-8 md:px-6 md:py-10">
        <div className="rounded-[1.75rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-8">
          <p className="font-medium text-[var(--lesson-text)] text-lg">
            Kana overview is unavailable
          </p>
          <p className="mt-2 text-[var(--lesson-text-muted)] text-sm">
            {overviewQuery.error instanceof Error ? overviewQuery.error.message : "Try again."}
          </p>
          <button
            className={`mt-6 ${PRIMARY_BUTTON_CLASS} disabled:cursor-not-allowed disabled:opacity-60`}
            disabled={overviewQuery.isFetching}
            onClick={() => {
              void overviewQuery.refetch();
            }}
            type="button"
          >
            {overviewQuery.isFetching ? "Loading…" : "Try again"}
          </button>
        </div>
      </div>
    );
  }

  const overview = overviewQuery.data;

  return (
    <div className="space-y-6 px-4 py-6 md:px-6 md:py-8">
      <section className="overflow-hidden rounded-[2rem] border border-[var(--lesson-border)] bg-[radial-gradient(circle_at_top_left,rgba(23,122,109,0.18),transparent_38%),linear-gradient(135deg,#fffdf8_0%,#f5fbf8_55%,#eef7ff_100%)] p-6 md:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="font-mono text-[11px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
              Kana track
            </p>
            <h1 className="mt-3 font-semibold text-4xl text-[var(--lesson-text)] tracking-[-0.04em] md:text-5xl">
              Learn hiragana and katakana.
            </h1>
            <p className="mt-4 max-w-xl text-[var(--lesson-text-muted)] leading-7">
              Tap a character to hear it.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-[1.35rem] border border-white/70 bg-white/70 px-4 py-4 backdrop-blur">
              <p className="text-[var(--lesson-text-soft)] text-xs uppercase tracking-[0.2em]">
                Mastered
              </p>
              <p className="mt-2 font-semibold text-3xl text-[var(--lesson-text)]">
                {overview.mastered_characters}
              </p>
            </div>
            <div className="rounded-[1.35rem] border border-white/70 bg-white/70 px-4 py-4 backdrop-blur">
              <p className="text-[var(--lesson-text-soft)] text-xs uppercase tracking-[0.2em]">
                Total
              </p>
              <p className="mt-2 font-semibold text-3xl text-[var(--lesson-text)]">
                {overview.total_characters}
              </p>
            </div>
            <div className="rounded-[1.35rem] border border-white/70 bg-white/70 px-4 py-4 backdrop-blur">
              <p className="text-[var(--lesson-text-soft)] text-xs uppercase tracking-[0.2em]">
                Coverage
              </p>
              <p className="mt-2 font-semibold text-3xl text-[var(--lesson-text)]">
                {masteredPercent}%
              </p>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            className={`${PRIMARY_BUTTON_CLASS} inline-flex items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60`}
            disabled={continueMutation.isPending}
            onClick={() => {
              void handleContinue();
            }}
            type="button"
          >
            {continueMutation.isPending ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {overview.current_lesson_id ? "Continue learning" : "Start learning"}
          </button>
        </div>
      </section>

      <section className="rounded-[1.75rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-5 md:p-6">
        {playbackError ? (
          <p className="mb-4 text-[var(--lesson-error-accent)] text-sm" role="alert">
            {playbackError}
          </p>
        ) : null}
        <div className="grid grid-cols-2 gap-4 border-[var(--lesson-border)] border-b pb-6">
          <div className="text-center">
            <h2 className="font-semibold text-2xl text-[var(--lesson-text)] tracking-[-0.03em]">
              Hiragana
            </h2>
            <p className="mt-1 text-[var(--lesson-text-soft)] text-sm">ひらがな</p>
          </div>
          <div className="text-center">
            <h2 className="font-semibold text-2xl text-[var(--lesson-text)] tracking-[-0.03em]">
              Katakana
            </h2>
            <p className="mt-1 text-[var(--lesson-text-soft)] text-sm">カタカナ</p>
          </div>
        </div>

        <div className="mt-6 space-y-6">
          {groupRows.map((row) => (
            <div className="grid grid-cols-2 gap-4" key={row.groupKey}>
              {(["hiragana", "katakana"] as const).map((side) => (
                <div
                  className="flex w-full min-w-0 flex-wrap content-start justify-center gap-2"
                  key={side}
                >
                  {row[side].map((character) => (
                    <button
                      className={`flex aspect-[5/6] w-14 shrink-0 flex-col rounded-xl border px-2 pt-2 pb-2 transition sm:w-16 ${kanaOverviewTileClassName(character)} disabled:cursor-default`}
                      disabled={!isKanaOverviewTileTappable(character)}
                      key={character.character_id}
                      onClick={() => {
                        void playAudio(character.audio_url);
                      }}
                      title={
                        isKanaOverviewTileTappable(character)
                          ? undefined
                          : "Audio not available for this character"
                      }
                      type="button"
                    >
                      <div className="flex min-h-0 flex-1 items-center justify-center">
                        <p className="text-center font-semibold text-2xl leading-none sm:text-[1.65rem]">
                          {character.char}
                        </p>
                      </div>
                      <div className="mt-1 h-1 shrink-0 overflow-hidden rounded-full bg-black/10">
                        <div
                          className="h-full rounded-full bg-current"
                          style={{
                            width: `${characterProgressPercent(character)}%`,
                          }}
                        />
                      </div>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
