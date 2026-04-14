import { useNavigate } from "@tanstack/react-router";
import { AnimatePresence, LayoutGroup, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

import { authedRequestHeaders } from "../../shared/api";
import { PRIMARY_BUTTON_CLASS } from "../../shared/ui/tokens/button-classes";
import { LESSON_PAGE_SHELL_CLASS } from "./lib/layout";
import { isMultipleChoiceItem } from "./model/item-helpers";
import { lessonItemLabel } from "./model/item-label";
import { useLessonSession } from "./model/use-lesson-session";
import { LessonBottomZone, type LessonBottomZoneProps } from "./ui/bottom-zone";
import { LessonCompleteScreen } from "./ui/complete-screen";
import { MultipleChoiceExercise } from "./ui/exercise-multiple-choice";
import { WordBankExercise } from "./ui/exercise-word-bank";
import { LeaveLessonDialog } from "./ui/leave-dialog";
import { LessonItemMotionSection } from "./ui/lesson-item-motion-section";
import { HintablePrompt } from "./ui/prompt";
import { LessonTopBar } from "./ui/top-bar";

type LessonScreenProps = {
  lessonId: string;
};

/** Composed main-course lesson UI (route layer should only pass `lessonId`). */
export function LessonScreen({ lessonId }: LessonScreenProps) {
  const navigate = useNavigate();
  const {
    currentItem,
    selectedTiles,
    selectedOption,
    selectOption,
    addTile,
    removeTileAt,
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
    selectedTileInstances,
    availableTileInstances,
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
  } = useLessonSession(lessonId);

  const prefersReducedMotion = useReducedMotion();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioObjectUrlRef = useRef<string | null>(null);
  const [isSentenceAudioPlaying, setIsSentenceAudioPlaying] = useState(false);

  const resetAudioPlayback = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioObjectUrlRef.current) {
      URL.revokeObjectURL(audioObjectUrlRef.current);
      audioObjectUrlRef.current = null;
    }
    setIsSentenceAudioPlaying(false);
  }, []);

  useEffect(() => {
    return () => {
      resetAudioPlayback();
    };
  }, [resetAudioPlayback]);

  useEffect(() => {
    if (currentItem?.item_id === undefined) {
      setIsSentenceAudioPlaying(false);
    }
    resetAudioPlayback();
  }, [currentItem?.item_id, resetAudioPlayback]);

  const playAudioUrl = async (audioUrl: string, options?: { isSentenceAudio?: boolean }) => {
    if (!audioUrl) {
      return;
    }
    resetAudioPlayback();

    if (options?.isSentenceAudio) {
      setIsSentenceAudioPlaying(true);
    }

    try {
      const requestHeaders = authedRequestHeaders();
      const response = await fetch(audioUrl, {
        ...(requestHeaders ? { headers: requestHeaders } : {}),
      });
      if (!response.ok) {
        throw new Error(`Audio request failed with status ${response.status}`);
      }
      const audioBlob = await response.blob();
      const objectUrl = URL.createObjectURL(audioBlob);
      audioObjectUrlRef.current = objectUrl;
      const nextAudio = new Audio(objectUrl);
      nextAudio.addEventListener("ended", () => {
        if (options?.isSentenceAudio) {
          setIsSentenceAudioPlaying(false);
        }
      });
      nextAudio.addEventListener("error", () => {
        if (options?.isSentenceAudio) {
          setIsSentenceAudioPlaying(false);
        }
      });
      audioRef.current = nextAudio;
      await nextAudio.play();
    } catch {
      if (options?.isSentenceAudio) {
        setIsSentenceAudioPlaying(false);
      }
    }
  };

  const playSentenceAudio = async () => {
    const audioUrl = currentItem?.sentence_audio_url;
    if (!audioUrl) {
      return;
    }
    await playAudioUrl(audioUrl, { isSentenceAudio: true });
  };

  const goToPath = () => {
    void navigate({ to: "/path" });
  };

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
          <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.045)] md:px-10 md:py-10">
            <p className="font-medium text-[var(--lesson-text-soft)] text-sm">
              Preparing lesson...
            </p>
            <div className="mt-5 h-2 overflow-hidden rounded-full bg-[var(--lesson-border-soft)]">
              <div className="h-full w-1/3 animate-pulse rounded-full bg-[var(--lesson-accent)]" />
            </div>
            <p className="mt-5 text-[var(--lesson-text-muted)]">Loading next set...</p>
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
          <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.045)] md:px-10 md:py-10">
            <p className="font-medium text-[var(--lesson-text-soft)] text-sm">
              Could not load lesson
            </p>
            <p className="mt-3 text-[var(--lesson-error-accent)] text-sm leading-6">{initError}</p>
            <button
              className={`mt-6 ${PRIMARY_BUTTON_CLASS}`}
              onClick={retryInitLoad}
              type="button"
            >
              Try again
            </button>
          </section>
        </main>
        <LeaveLessonDialog
          isOpen={isLeaveDialogOpen}
          onCancel={closeLeaveDialog}
          onConfirm={() => {
            closeLeaveDialog();
            goToPath();
          }}
        />
      </div>
    );
  }

  if (isLessonFinished) {
    return (
      <div className={LESSON_PAGE_SHELL_CLASS}>
        <LessonTopBar
          onBack={goToPath}
          progressFillCompletedCount={progressBarFillCompletedCount}
          reviewCount={0}
          stepLabelIndex={currentIndex}
          totalCount={totalCount}
        />
        <LessonCompleteScreen
          completionProgressState={completionProgressState}
          correctCount={correctCount}
          mistakeCount={mistakeCount}
          onBackToPath={goToPath}
        />
      </div>
    );
  }

  if (!currentItem) {
    return (
      <div className={`${LESSON_PAGE_SHELL_CLASS} px-4 py-8 md:px-8`}>
        <div className="mx-auto max-w-4xl rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-8 shadow-[0_12px_30px_rgba(22,28,37,0.05)]">
          Lesson is unavailable.
        </div>
      </div>
    );
  }

  const bottomZoneProps: LessonBottomZoneProps = feedback
    ? {
        feedback,
        onContinue: () => {
          void advanceQueue();
        },
        continuePending,
        continueError: continueFooterError,
      }
    : {
        feedback: null,
        canCheck,
        onCheck: () => {
          void handleCheck();
        },
        checkError: checkAnswerError,
        checkPending: isCheckAnswerPending,
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
        <AnimatePresence initial={false} mode="wait">
          <LessonItemMotionSection
            key={currentItem.item_id}
            className="rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.045)] md:px-10 md:py-10"
            itemKey={currentItem.item_id}
            motionY={{ exit: -4, initial: 6 }}
            prefersReducedMotion={prefersReducedMotion}
          >
            <div className="mx-auto max-w-[48rem]">
              <p className="font-medium text-[0.8rem] text-[var(--lesson-text-faint)] tracking-[0.01em]">
                {lessonItemLabel(currentItem.item_type)}
              </p>

              <div className="mt-4">
                {currentItem.sentence_audio_url ? (
                  <button
                    className="mb-4 inline-flex items-center rounded-full border border-[var(--lesson-border-soft)] bg-[var(--lesson-surface)] px-4 py-2 font-medium text-[0.92rem] text-[var(--lesson-text-soft)] transition-colors duration-150 hover:border-[var(--lesson-accent)]/60 hover:text-[var(--lesson-text)]"
                    onClick={() => {
                      void playSentenceAudio();
                    }}
                    type="button"
                  >
                    {isSentenceAudioPlaying ? "Replay audio" : "Play audio"}
                  </button>
                ) : null}
                <HintablePrompt
                  onPlayTokenAudio={(audioUrl) => {
                    void playAudioUrl(audioUrl);
                  }}
                  promptText={currentItem.prompt_text}
                  tokens={
                    currentItem.prompt_lang === "ja"
                      ? currentItem.sentence_ja_tokens
                      : currentItem.sentence_en_tokens
                  }
                />
              </div>

              <div className="mt-8">
                <LayoutGroup>
                  {isMultipleChoiceItem(currentItem) ? (
                    <MultipleChoiceExercise
                      currentItem={currentItem}
                      feedback={feedback}
                      selectOption={selectOption}
                      selectedOption={selectedOption}
                    />
                  ) : (
                    <WordBankExercise
                      availableTileInstances={availableTileInstances}
                      feedback={feedback}
                      selectedTileInstances={selectedTileInstances}
                      selectedTiles={selectedTiles}
                      addTile={addTile}
                      removeTileAt={removeTileAt}
                    />
                  )}
                </LayoutGroup>
              </div>

              <LessonBottomZone {...bottomZoneProps} />
            </div>
          </LessonItemMotionSection>
        </AnimatePresence>
      </main>

      <LeaveLessonDialog
        isOpen={isLeaveDialogOpen}
        onCancel={closeLeaveDialog}
        onConfirm={() => {
          closeLeaveDialog();
          goToPath();
        }}
      />
    </div>
  );
}
