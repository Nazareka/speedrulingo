import { useNavigate, useParams } from "@tanstack/react-router";
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "framer-motion";
import { LessonBottomZone, type LessonBottomZoneProps } from "./bottom-zone";
import { LessonCompleteScreen } from "./complete-screen";
import { MultipleChoiceExercise } from "./exercise-multiple-choice";
import { WordBankExercise } from "./exercise-word-bank";
import { isMultipleChoiceItem } from "./item-helpers";
import { lessonItemLabel } from "./item-label";
import { LeaveLessonDialog } from "./leave-dialog";
import { HintablePrompt } from "./prompt";
import { LessonTopBar } from "./top-bar";
import { PRIMARY_BUTTON_CLASS, QUICK_TRANSITION } from "./ui-constants";
import { useLessonSession } from "./use-session";

const LESSON_PAGE_SHELL_CLASS =
  "min-h-screen bg-[var(--lesson-bg)] font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-stone-900";

export function LessonPage() {
  const params = useParams({ from: "/lesson/$lessonId" });
  const lessonId = params.lessonId;
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
            void navigate({ to: "/path" });
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
            void navigate({ to: "/path" });
          }}
          progressFillCompletedCount={progressBarFillCompletedCount}
          reviewCount={0}
          stepLabelIndex={currentIndex}
          totalCount={totalCount}
        />
        <LessonCompleteScreen
          completionProgressState={completionProgressState}
          correctCount={correctCount}
          mistakeCount={mistakeCount}
          onBackToPath={() => {
            void navigate({ to: "/path" });
          }}
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
          <motion.section
            animate={{ opacity: 1, y: 0 }}
            className="rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.045)] md:px-10 md:py-10"
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -4 }}
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
            key={currentItem.item_id}
            transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
          >
            <div className="mx-auto max-w-[48rem]">
              <p className="font-medium text-[0.8rem] text-[var(--lesson-text-faint)] tracking-[0.01em]">
                {lessonItemLabel(currentItem.item_type)}
              </p>

              <div className="mt-4">
                <HintablePrompt
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
          </motion.section>
        </AnimatePresence>
      </main>

      <LeaveLessonDialog
        isOpen={isLeaveDialogOpen}
        onCancel={closeLeaveDialog}
        onConfirm={() => {
          closeLeaveDialog();
          void navigate({ to: "/path" });
        }}
      />
    </div>
  );
}
