import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { AnimatePresence, useReducedMotion } from "framer-motion";
import { Volume2 } from "lucide-react";
import { useState } from "react";

import {
  useKanaLessonAudioToKanaAutoplay,
  useKanaLessonKanaToAudioIncorrectAutoplay,
  useKanaLessonMountPrefetch,
  useKanaLessonPlayback,
  usePrefetchKanaLessonItemAudio,
} from "../features/kana/use-kana-lesson-page-audio";
import { useKanaLessonSession } from "../features/kana/use-kana-lesson-session";
import { LessonFeedbackOrCheckMotionZone } from "../shared/lesson/feedback-or-check-motion-zone";
import { LessonFeedbackTray } from "../shared/lesson/feedback-tray";
import { LESSON_PAGE_SHELL_CLASS } from "../shared/lesson/layout";
import { LeaveLessonDialog } from "../shared/lesson/leave-dialog";
import { LessonItemMotionSection } from "../shared/lesson/lesson-item-motion-section";
import { LESSON_ANSWER_CONTROL } from "../shared/lesson/shortcuts";
import { LessonSprintCompleteSummary } from "../shared/lesson/sprint-complete-summary";
import { LessonTopBar } from "../shared/lesson/top-bar";
import { PRIMARY_BUTTON_CLASS } from "../shared/lesson/ui-constants";

const OPTION_ICON_CLASS = "h-12 w-12 md:h-14 md:w-14";

export function KanaLessonPage() {
  const { lessonId } = useParams({ from: "/kana/lesson/$lessonId" });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const prefersReducedMotion = useReducedMotion();
  const {
    currentItem,
    selectedOptionId,
    selectOption,
    feedback,
    correctCount,
    mistakeCount,
    isLessonFinished,
    completionProgressState,
    isInitializing,
    initError,
    isLeaveDialogOpen,
    openLeaveDialog,
    closeLeaveDialog,
    retryInitLoad,
    canCheck,
    totalCount,
    currentIndex,
    progressBarFillCompletedCount,
    remainingReviewCount,
    checkAnswerError,
    continueFooterError,
    continuePending,
    isCheckAnswerPending,
    advanceQueue,
    handleCheck,
  } = useKanaLessonSession(lessonId);

  useKanaLessonMountPrefetch(queryClient);
  const { playAudio, audioBusy } = useKanaLessonPlayback(currentItem);
  usePrefetchKanaLessonItemAudio(currentItem);
  useKanaLessonAudioToKanaAutoplay(currentItem, feedback, playAudio, prefersReducedMotion);
  useKanaLessonKanaToAudioIncorrectAutoplay(feedback, currentItem, playAudio, prefersReducedMotion);

  const [audioPlaybackError, setAudioPlaybackError] = useState<string | null>(null);

  if (isInitializing) {
    return (
      <div className={LESSON_PAGE_SHELL_CLASS}>
        <LessonTopBar
          onBack={openLeaveDialog}
          progressFillCompletedCount={0}
          reviewCount={0}
          stepLabelIndex={0}
          totalCount={1}
        />
        <main className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-10">
          <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8">
            <p className="text-[var(--lesson-text-soft)] text-sm">Preparing kana lesson...</p>
          </section>
        </main>
      </div>
    );
  }

  if (initError) {
    return (
      <div className={LESSON_PAGE_SHELL_CLASS}>
        <LessonTopBar
          onBack={openLeaveDialog}
          progressFillCompletedCount={0}
          reviewCount={0}
          stepLabelIndex={0}
          totalCount={1}
        />
        <main className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-10">
          <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8">
            <p className="font-medium text-[var(--lesson-text)] text-lg">
              Kana lesson is unavailable
            </p>
            <p className="mt-3 text-[var(--lesson-error-accent)] text-sm">{initError}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button className={PRIMARY_BUTTON_CLASS} onClick={retryInitLoad} type="button">
                Try again
              </button>
              <button
                className="rounded-full border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-5 py-2.5 font-semibold text-[var(--lesson-text)] text-sm transition hover:bg-[var(--lesson-surface-muted)]"
                onClick={() => {
                  void navigate({ to: "/kana" });
                }}
                type="button"
              >
                Back to kana
              </button>
            </div>
          </section>
        </main>
        <LeaveLessonDialog
          isOpen={isLeaveDialogOpen}
          onCancel={closeLeaveDialog}
          onConfirm={() => {
            closeLeaveDialog();
            void navigate({ to: "/kana" });
          }}
        />
      </div>
    );
  }

  if (isLessonFinished) {
    return (
      <div className={LESSON_PAGE_SHELL_CLASS}>
        <LessonTopBar
          onBack={() => {
            void navigate({ to: "/kana" });
          }}
          progressFillCompletedCount={progressBarFillCompletedCount}
          reviewCount={0}
          stepLabelIndex={currentIndex}
          totalCount={totalCount}
        />
        <main className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-10">
          <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.05)] md:px-10 md:py-10">
            <LessonSprintCompleteSummary
              accentLabel="Kana sprint complete"
              completionProgressState={completionProgressState}
              correctCount={correctCount}
              footer={
                <button
                  className={PRIMARY_BUTTON_CLASS}
                  onClick={() => {
                    void navigate({ to: "/kana" });
                  }}
                  type="button"
                >
                  Back to kana
                </button>
              }
              mistakeCount={mistakeCount}
            />
          </section>
        </main>
      </div>
    );
  }

  if (!currentItem) {
    return (
      <div className={`${LESSON_PAGE_SHELL_CLASS} px-4 py-8 md:px-8`}>
        <div className="mx-auto max-w-4xl rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-8">
          <p className="font-medium text-[var(--lesson-text)] text-lg">
            Kana lesson is unavailable
          </p>
          <p className="mt-2 text-[var(--lesson-text-muted)] text-sm">
            No lesson items were returned. Open the kana overview and start or continue a lesson.
          </p>
          <button
            className={`mt-6 ${PRIMARY_BUTTON_CLASS}`}
            onClick={() => {
              void navigate({ to: "/kana" });
            }}
            type="button"
          >
            Back to kana
          </button>
        </div>
      </div>
    );
  }

  const correctOptionAudioUrl =
    feedback && !feedback.isCorrect && currentItem.item_type === "kana_to_audio_choice"
      ? currentItem.answer_options.find((option) => option.char === feedback.expectedAnswer)
          ?.audio_url
      : undefined;

  const playAudioWithError = async (url: string | null | undefined) => {
    setAudioPlaybackError(null);
    try {
      await playAudio(url);
    } catch {
      setAudioPlaybackError("Could not play audio. Try again or check your connection.");
    }
  };

  return (
    <div className={`${LESSON_PAGE_SHELL_CLASS} pb-12`}>
      <LessonTopBar
        onBack={openLeaveDialog}
        progressFillCompletedCount={progressBarFillCompletedCount}
        reviewCount={remainingReviewCount}
        stepLabelIndex={currentIndex}
        totalCount={totalCount}
      />

      <main className="mx-auto max-w-5xl px-4 py-6 md:px-6 md:py-8">
        {audioPlaybackError ? (
          <p className="mb-4 text-[var(--lesson-error-accent)] text-sm" role="alert">
            {audioPlaybackError}
          </p>
        ) : null}
        <AnimatePresence initial={false} mode="wait">
          <LessonItemMotionSection
            className="rounded-[1.75rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-6 shadow-[0_12px_30px_rgba(22,28,37,0.05)] md:p-8"
            itemKey={currentItem.item_id}
            motionY={{ exit: 8, initial: 12 }}
            prefersReducedMotion={prefersReducedMotion}
          >
            <p className="font-mono text-[11px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
              {currentItem.item_type === "audio_to_kana_choice" ? "Audio to kana" : "Kana to audio"}
            </p>
            <h1 className="mt-3 text-center font-semibold text-3xl text-[var(--lesson-text)] tracking-[-0.03em] md:text-4xl">
              {currentItem.item_type === "audio_to_kana_choice"
                ? "Pick the character that matches the sound."
                : "Pick the sound that matches the character."}
            </h1>

            {currentItem.item_type === "audio_to_kana_choice" ? (
              <div className="mt-10 flex justify-center">
                <button
                  className="inline-flex items-center justify-center rounded-2xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-4 text-[var(--lesson-accent)] transition hover:bg-[var(--lesson-surface-muted)]"
                  onClick={() => {
                    void playAudioWithError(currentItem.prompt_audio_url);
                  }}
                  type="button"
                >
                  <Volume2
                    className={`h-10 w-10 ${audioBusy ? "motion-safe:animate-pulse" : ""}`}
                  />
                </button>
              </div>
            ) : (
              <div className="mt-10 flex justify-center">
                <p className="text-center text-[5rem] text-[var(--lesson-text)] leading-none md:text-[6rem]">
                  {currentItem.prompt_char}
                </p>
              </div>
            )}

            <div className="mx-auto mt-10 grid w-full max-w-[min(100%,20rem)] grid-cols-2 gap-3 sm:max-w-[22rem]">
              {currentItem.answer_options.map((option) => {
                const selected = selectedOptionId === option.option_id;
                return (
                  <button
                    {...{ [LESSON_ANSWER_CONTROL]: "" }}
                    className={`flex aspect-square w-full flex-col items-center justify-center rounded-2xl border p-4 transition ${
                      selected
                        ? "border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] text-[var(--lesson-accent)]"
                        : "border-[var(--lesson-border)] bg-[var(--lesson-surface)] text-[var(--lesson-text)] hover:bg-[var(--lesson-surface-muted)]"
                    }`}
                    disabled={feedback !== null}
                    key={option.option_id}
                    onClick={() => {
                      selectOption(option.option_id);
                      if (currentItem.item_type === "kana_to_audio_choice") {
                        void playAudioWithError(option.audio_url);
                      }
                    }}
                    type="button"
                  >
                    {currentItem.item_type === "audio_to_kana_choice" ? (
                      <span className="text-5xl leading-none md:text-6xl">{option.char}</span>
                    ) : (
                      <Volume2 className={`${OPTION_ICON_CLASS} shrink-0`} />
                    )}
                  </button>
                );
              })}
            </div>

            <LessonFeedbackOrCheckMotionZone
              checkSlot={
                <>
                  {checkAnswerError ? (
                    <span className="text-[var(--lesson-error-accent)] text-sm">
                      {checkAnswerError}
                    </span>
                  ) : null}

                  <button
                    className={`min-w-[9.5rem] ${PRIMARY_BUTTON_CLASS} disabled:cursor-not-allowed disabled:bg-[var(--lesson-disabled-bg)]`}
                    disabled={!canCheck}
                    onClick={() => {
                      void handleCheck();
                    }}
                    type="button"
                  >
                    {isCheckAnswerPending ? "Checking..." : "Check"}
                  </button>
                </>
              }
              feedbackSlot={
                feedback ? (
                  <LessonFeedbackTray
                    continueError={continueFooterError}
                    continuePending={continuePending}
                    feedback={feedback}
                    kanaIncorrectAudio={{
                      correctOptionAudioUrl,
                      correctSoundBusy: audioBusy,
                      itemType: currentItem.item_type,
                      onPlayCorrectSound: () => {
                        void playAudioWithError(correctOptionAudioUrl);
                      },
                    }}
                    onContinue={() => {
                      void advanceQueue();
                    }}
                  />
                ) : null
              }
              hasFeedback={feedback !== null}
            />
          </LessonItemMotionSection>
        </AnimatePresence>
      </main>

      <LeaveLessonDialog
        isOpen={isLeaveDialogOpen}
        onCancel={closeLeaveDialog}
        onConfirm={() => {
          closeLeaveDialog();
          void navigate({ to: "/kana" });
        }}
      />
    </div>
  );
}
