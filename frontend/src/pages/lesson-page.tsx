import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "framer-motion";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useNextItemMutation, useSubmitLessonMutation } from "../features/lesson-runner/queries";
import { pathKeys } from "../features/path/queries";
import { unitKeys } from "../features/units/queries";
import type { LessonItemResponse, SentenceTokenPreview } from "../shared/api/generated/types.gen";
import { getErrorMessage } from "../shared/lib/api-error";

type FeedbackState = {
  expectedAnswer: string;
  isCorrect: boolean;
  submittedAnswer: string;
};

type QueueEntry = {
  itemId: string;
  source: "main" | "review";
};

type TileInstance = {
  id: string;
  text: string;
};

function isMultipleChoiceItem(
  item: LessonItemResponse | null | undefined,
): item is LessonItemResponse {
  return item?.item_type === "word_choice" || item?.item_type === "kanji_kana_match";
}

function lessonItemLabel(itemType: LessonItemResponse["item_type"]) {
  if (itemType === "word_choice") {
    return "Word match";
  }
  if (itemType === "kanji_kana_match") {
    return "Match kanji and kana";
  }
  return "Build a sentence";
}

function normalizeAnswer(parts: Array<string>): string {
  return parts.join(" ").trim();
}

function buildTileInstances(tiles: Array<string>): Array<TileInstance> {
  const counts = new Map<string, number>();
  return tiles.map((tile) => {
    const count = counts.get(tile) ?? 0;
    counts.set(tile, count + 1);
    return {
      id: `${tile}-${count}`,
      text: tile,
    };
  });
}

function stableShuffle<T>(items: Array<T>, seed: string): Array<T> {
  return items
    .map((item, index) => {
      let hash = 2166136261;
      const input = `${seed}:${index}:${String(item)}`;
      for (let i = 0; i < input.length; i += 1) {
        hash ^= input.charCodeAt(i);
        hash = Math.imul(hash, 16777619);
      }
      return { item, hash: hash >>> 0 };
    })
    .sort((left, right) => left.hash - right.hash)
    .map(({ item }) => item);
}

function progressWidth(completedUniqueItems: number, totalItems: number) {
  const safeTotal = Math.max(totalItems, 1);
  const percent = (completedUniqueItems / safeTotal) * 100;
  return `${Math.max(0, Math.min(percent, 100))}%`;
}

function isLikelyJapaneseText(text: string) {
  return /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]/u.test(text);
}

function optionTypographyClass(text: string) {
  return isLikelyJapaneseText(text)
    ? "font-['Noto_Sans_JP','Hiragino_Sans','Yu_Gothic','Meiryo',sans-serif] text-[1.24rem] leading-7"
    : "text-[1.16rem] leading-7";
}

function promptTypographyClass(text: string) {
  return isLikelyJapaneseText(text)
    ? "font-['Noto_Sans_JP','Hiragino_Sans','Yu_Gothic','Meiryo',sans-serif] text-[2.2rem] font-semibold leading-[1.22] tracking-[-0.035em] md:text-[2.9rem]"
    : "text-[1.8rem] font-semibold leading-[1.1] tracking-[-0.04em] md:text-[2.4rem]";
}

const PRIMARY_BUTTON_CLASS =
  "rounded-[1rem] bg-[var(--lesson-accent)] px-7 py-3.5 font-semibold text-[0.95rem] text-white tracking-[-0.01em] shadow-[0_8px_18px_rgba(23,122,109,0.12)] transition hover:bg-[var(--lesson-accent-hover)] active:scale-[0.985]";

const SECONDARY_BUTTON_CLASS =
  "rounded-[1rem] border border-[var(--lesson-border-strong)] bg-[var(--lesson-surface)] px-5 py-3 font-medium text-[var(--lesson-text-muted)] text-sm transition hover:bg-[var(--lesson-surface-muted)] active:scale-[0.985]";

const FAST_TRANSITION = { duration: 0.1, ease: "easeOut" } as const;
const QUICK_TRANSITION = { duration: 0.12, ease: "easeOut" } as const;

function answerStateClasses(
  isSelected: boolean,
  feedback: FeedbackState | null,
  option: string,
  expectedAnswer: string,
) {
  if (!feedback) {
    return isSelected
      ? "border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] text-[var(--lesson-text)] shadow-[0_12px_26px_rgba(23,122,109,0.10)]"
      : "border-[var(--lesson-border)] bg-[var(--lesson-surface)] text-[var(--lesson-text)] hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface)] hover:shadow-[0_10px_22px_rgba(35,48,54,0.05)]";
  }

  if (option === expectedAnswer) {
    return "border-[var(--lesson-success-border)] bg-[var(--lesson-success-bg)] text-[var(--lesson-text)] shadow-[0_10px_20px_rgba(76,141,118,0.07)]";
  }

  if (isSelected && !feedback.isCorrect) {
    return "border-[var(--lesson-error-border)] bg-[var(--lesson-error-bg)] text-[var(--lesson-text)] shadow-[0_10px_20px_rgba(170,112,92,0.06)]";
  }

  return "border-[var(--lesson-border-soft)] bg-[var(--lesson-muted-bg)] text-[var(--lesson-muted-text)]";
}

function LessonTopBar(props: {
  currentIndex: number;
  onBack: () => void;
  reviewCount: number;
  totalCount: number;
}) {
  const { currentIndex, onBack, reviewCount, totalCount } = props;
  const progressValue = progressWidth(Math.max(currentIndex - 1, 0), totalCount);
  const prefersReducedMotion = useReducedMotion();

  return (
    <header className="sticky top-0 z-30 border-[var(--lesson-border)] border-b bg-[color:var(--lesson-bg)]/96 backdrop-blur">
      <div className="mx-auto grid max-w-5xl grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3.5 md:px-6">
        <button
          className="inline-flex h-11 items-center gap-2 rounded-[1rem] border border-[var(--lesson-border-strong)] bg-[var(--lesson-surface)] px-4 font-medium text-[var(--lesson-text-muted)] text-sm transition hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface-muted)]"
          onClick={onBack}
          type="button"
        >
          <span aria-hidden="true">←</span>
          Leave
        </button>

        <div className="min-w-0">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--lesson-border-soft)]">
            <motion.div
              animate={{ width: progressValue }}
              className="h-full rounded-full bg-[var(--lesson-accent)]"
              initial={false}
              transition={prefersReducedMotion ? { duration: 0 } : FAST_TRANSITION}
            />
          </div>
        </div>

        <div className="shrink-0 text-right font-medium text-[var(--lesson-text-soft)] text-sm tabular-nums">
          {currentIndex} / {totalCount} · Review {reviewCount}
        </div>
      </div>
    </header>
  );
}

function LeaveLessonDialog(props: {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const { isOpen, onCancel, onConfirm } = props;

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-stone-950/35 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-[1.4rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-6 shadow-[0_24px_56px_rgba(22,28,37,0.16)]">
        <p className="font-medium text-[var(--lesson-text-soft)] text-sm">Leave lesson</p>
        <h2 className="mt-3 font-semibold text-2xl text-[var(--lesson-text)] tracking-[-0.03em]">
          Stop this sprint now?
        </h2>
        <p className="mt-3 text-[var(--lesson-text-muted)] text-sm leading-6">
          Your progress in this lesson may be lost. You can keep learning or leave and return to the
          path.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button className={`flex-1 ${PRIMARY_BUTTON_CLASS}`} onClick={onCancel} type="button">
            Keep learning
          </button>
          <button className={`flex-1 ${SECONDARY_BUTTON_CLASS}`} onClick={onConfirm} type="button">
            Leave
          </button>
        </div>
      </div>
    </div>
  );
}

function LessonCompleteScreen(props: {
  completionProgressState: string | null;
  correctCount: number;
  mistakeCount: number;
  onBackToPath: () => void;
}) {
  const { completionProgressState, correctCount, mistakeCount, onBackToPath } = props;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 md:px-6 md:py-10">
      <section className="rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-6 py-8 shadow-[0_12px_30px_rgba(22,28,37,0.05)] md:px-10 md:py-10">
        <p className="font-medium text-[var(--lesson-accent)] text-sm">
          Speedrulingo sprint complete
        </p>

        <h1 className="mt-3 font-semibold text-4xl text-[var(--lesson-text)] tracking-[-0.03em] md:text-5xl">
          {mistakeCount === 0 ? "Clean finish." : "Every item solved."}
        </h1>

        <p className="mt-4 max-w-2xl text-[var(--lesson-text-muted)] text-base leading-7">
          Correct checks: {correctCount}. Review fixes: {mistakeCount}. Progress state:{" "}
          {(completionProgressState ?? "completed").replace("_", " ")}.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
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

        <div className="mt-8">
          <button className={PRIMARY_BUTTON_CLASS} onClick={onBackToPath} type="button">
            Back to path
          </button>
        </div>
      </section>
    </div>
  );
}

function AnswerCard(props: {
  disabled: boolean;
  feedback: FeedbackState | null;
  isSelected: boolean;
  onSelect: () => void;
  option: string;
}) {
  const { disabled, feedback, isSelected, onSelect, option } = props;
  const expectedAnswer = feedback?.expectedAnswer ?? "";
  const tone = answerStateClasses(isSelected, feedback, option, expectedAnswer);
  const interactionProps = disabled
    ? {}
    : {
        whileHover: { y: -0.5 },
        whileTap: { scale: 0.994 },
      };

  return (
    <motion.button
      animate={
        feedback
          ? option === expectedAnswer
            ? { scale: 1, y: 0, opacity: 1 }
            : isSelected && !feedback.isCorrect
              ? { scale: 1, y: 0, opacity: 1 }
              : { scale: 1, y: 0, opacity: 0.84 }
          : isSelected
            ? { scale: 1.008, y: -0.5 }
            : { scale: 1, y: 0, opacity: 1 }
      }
      aria-label={`${option}${feedback ? `, ${option === expectedAnswer ? "correct" : isSelected && !feedback.isCorrect ? "incorrect" : "not selected"}` : isSelected ? ", selected" : ""}`}
      className={`w-full rounded-[1.15rem] border px-6 py-[1.35rem] text-left transition duration-150 ${tone} ${
        disabled ? "pointer-events-none" : ""
      }`}
      initial={false}
      layout
      onClick={onSelect}
      transition={FAST_TRANSITION}
      type="button"
      {...interactionProps}
    >
      <div className="flex min-h-[2.75rem] items-center">
        <span
          className={`min-w-0 flex-1 font-medium tracking-[-0.01em] ${optionTypographyClass(option)}`}
        >
          {option}
        </span>
      </div>
    </motion.button>
  );
}

function MultipleChoiceExercise(props: {
  currentItem: LessonItemResponse;
  feedback: FeedbackState | null;
  selectedOption: string | null;
  setSelectedOption: (value: string) => void;
}) {
  const { currentItem, feedback, selectedOption, setSelectedOption } = props;
  const optionInstances = useMemo(
    () =>
      buildTileInstances(
        stableShuffle(
          currentItem.answer_tiles,
          `${currentItem.item_id}:${currentItem.prompt_text}`,
        ),
      ),
    [currentItem.answer_tiles, currentItem.item_id, currentItem.prompt_text],
  );

  return (
    <div className="grid gap-3.5 md:grid-cols-2 md:gap-4">
      {optionInstances.map((optionInstance) => (
        <AnswerCard
          disabled={feedback !== null}
          feedback={feedback}
          isSelected={selectedOption === optionInstance.text}
          key={optionInstance.id}
          onSelect={() => setSelectedOption(optionInstance.text)}
          option={optionInstance.text}
        />
      ))}
    </div>
  );
}

function WordBankExercise(props: {
  availableTileInstances: Array<TileInstance>;
  feedback: FeedbackState | null;
  selectedTileInstances: Array<TileInstance>;
  selectedTiles: Array<string>;
  setSelectedTiles: Dispatch<SetStateAction<Array<string>>>;
}) {
  const {
    availableTileInstances,
    feedback,
    selectedTileInstances,
    selectedTiles,
    setSelectedTiles,
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
                  )} ${feedback ? "pointer-events-none opacity-70" : ""}`}
                  key={tileInstance.id}
                  onClick={() => {
                    if (feedback) {
                      return;
                    }
                    setSelectedTiles((current) =>
                      current.filter((_, currentIndex) => currentIndex !== index),
                    );
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
              className={`rounded-xl border border-[var(--lesson-border)] bg-[var(--lesson-surface)] px-4 py-2.5 font-medium text-[var(--lesson-text)] transition hover:border-[var(--lesson-border-hover)] hover:bg-[var(--lesson-surface-muted)] ${optionTypographyClass(
                tileInstance.text,
              )} ${feedback ? "pointer-events-none opacity-70" : ""}`}
              key={tileInstance.id}
              onClick={() => {
                if (feedback) {
                  return;
                }
                setSelectedTiles((current) => [...current, tileInstance.text]);
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

function LessonFooter(props: { feedback: FeedbackState | null; onContinue: () => void }) {
  const { feedback, onContinue } = props;

  const prefersReducedMotion = useReducedMotion();

  if (!feedback) {
    return null;
  }

  const trayTone = feedback.isCorrect
    ? "border-[var(--lesson-success-border)] bg-[var(--lesson-success-bg)]"
    : "border-[var(--lesson-error-border)] bg-[color:var(--lesson-error-bg)]";

  return (
    <AnimatePresence initial={false} mode="wait">
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-[1.15rem] border px-5 py-4 ${trayTone}`}
        exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 4 }}
        initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
        key="feedback-tray"
        transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
      >
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

          <button className={`shrink-0 ${PRIMARY_BUTTON_CLASS}`} onClick={onContinue} type="button">
            Continue
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function LessonBottomZone(props: {
  canCheck: boolean;
  feedback: FeedbackState | null;
  onCheck: () => void;
  onContinue: () => void;
  submitError: string | null;
  submitPending: boolean;
}) {
  const { canCheck, feedback, onCheck, onContinue, submitError, submitPending } = props;
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="mt-8 pt-2">
      <AnimatePresence initial={false} mode="wait">
        {feedback ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 4 }}
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
            key="feedback-zone"
            transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
          >
            <LessonFooter feedback={feedback} onContinue={onContinue} />
          </motion.div>
        ) : (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap items-center justify-end gap-3"
            exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 4 }}
            initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
            key="action-zone"
            transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
          >
            {submitError ? (
              <span className="text-[var(--lesson-error-accent)] text-sm">{submitError}</span>
            ) : null}

            <button
              className={`min-w-[9.5rem] ${PRIMARY_BUTTON_CLASS} disabled:cursor-not-allowed disabled:bg-[var(--lesson-disabled-bg)]`}
              disabled={!canCheck}
              onClick={onCheck}
              type="button"
            >
              {submitPending ? "Checking..." : "Check"}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function HintableToken(props: { token: SentenceTokenPreview }) {
  const { token } = props;
  const hints = token.hints ?? [];
  const hasHints = hints.length > 0;

  if (!hasHints) {
    return <span>{token.surface}</span>;
  }

  return (
    <span className="group/hint relative inline-block cursor-help pb-[5px] transition-colors duration-100 hover:bg-[var(--lesson-accent)]/[0.07]">
      {token.surface}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-[3px] bottom-0 h-[2px] rounded-full bg-[var(--lesson-accent)] opacity-20 transition-opacity duration-100 group-hover/hint:opacity-50"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-full left-1/2 z-40 mt-2 -translate-x-1/2 rounded-xl border border-[var(--lesson-border-soft)] bg-white px-4 py-2.5 opacity-0 shadow-[0_8px_24px_rgba(22,28,37,0.08)] transition-opacity duration-100 group-hover/hint:pointer-events-auto group-hover/hint:opacity-100"
      >
        <span className="flex flex-col">
          {hints.map((hint, i) => (
            <span
              className={`whitespace-nowrap font-normal text-[0.9rem] text-[var(--lesson-text-soft)] leading-relaxed tracking-normal ${
                i > 0 ? "mt-1.5 border-[var(--lesson-border-soft)]/60 border-t pt-1.5" : ""
              }`}
              key={hint}
            >
              {hint}
            </span>
          ))}
        </span>
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 border-[5px] border-transparent border-b-[var(--lesson-border-soft)]" />
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 translate-y-px border-[5px] border-transparent border-b-white" />
      </span>
    </span>
  );
}

function HintablePrompt(props: { promptText: string; tokens: Array<SentenceTokenPreview> }) {
  const { promptText, tokens } = props;
  const hasAnyHints = tokens.some((t) => t.hints && t.hints.length > 0);

  if (!hasAnyHints || tokens.length === 0) {
    return (
      <h1 className={`text-balance text-[var(--lesson-text)] ${promptTypographyClass(promptText)}`}>
        {promptText}
      </h1>
    );
  }

  const hasSpaces = promptText.includes(" ");

  return (
    <h1 className={`text-[var(--lesson-text)] ${promptTypographyClass(promptText)}`}>
      {tokens.map((token, i) => (
        <span key={token.token_index}>
          {hasSpaces && i > 0 ? " " : null}
          <HintableToken token={token} />
        </span>
      ))}
    </h1>
  );
}

export function LessonPage() {
  const params = useParams({ from: "/lesson/$lessonId" });
  const lessonId = params.lessonId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const nextItemMutation = useNextItemMutation(params.lessonId);
  const submitMutation = useSubmitLessonMutation(params.lessonId);
  const nextItemMutateAsyncRef = useRef(nextItemMutation.mutateAsync);
  const advanceQueueRef = useRef<() => Promise<void>>(async () => {});
  const handleCheckRef = useRef<() => Promise<void>>(async () => {});

  const [itemCache, setItemCache] = useState<Record<string, LessonItemResponse>>({});
  const [currentQueueEntry, setCurrentQueueEntry] = useState<QueueEntry | null>(null);
  const [mainQueue, setMainQueue] = useState<Array<QueueEntry>>([]);
  const [reviewQueue, setReviewQueue] = useState<Array<QueueEntry>>([]);
  const [nextCursorToLoad, setNextCursorToLoad] = useState(0);
  const [totalItems, setTotalItems] = useState<number | null>(null);
  const [completedItemIds, setCompletedItemIds] = useState<Array<string>>([]);
  const [finalAnswers, setFinalAnswers] = useState<Record<string, string>>({});
  const [selectedTiles, setSelectedTiles] = useState<Array<string>>([]);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [mistakeCount, setMistakeCount] = useState(0);
  const [isLessonFinished, setIsLessonFinished] = useState(false);
  const [completionProgressState, setCompletionProgressState] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isLeaveDialogOpen, setIsLeaveDialogOpen] = useState(false);

  const currentItem = currentQueueEntry ? itemCache[currentQueueEntry.itemId] : undefined;

  useEffect(() => {
    nextItemMutateAsyncRef.current = nextItemMutation.mutateAsync;
  }, [nextItemMutation.mutateAsync]);

  useEffect(() => {
    let isCancelled = false;

    async function initializeLesson() {
      const requestedLessonId = lessonId;
      setIsInitializing(true);
      setItemCache({});
      setCurrentQueueEntry(null);
      setMainQueue([]);
      setReviewQueue([]);
      setNextCursorToLoad(0);
      setTotalItems(null);
      setCompletedItemIds([]);
      setFinalAnswers({});
      setSelectedTiles([]);
      setSelectedOption(null);
      setFeedback(null);
      setCorrectCount(0);
      setMistakeCount(0);
      setIsLessonFinished(false);
      setCompletionProgressState(null);

      try {
        const firstItem = await nextItemMutateAsyncRef.current(0);
        if (isCancelled || requestedLessonId !== lessonId) {
          return;
        }
        setItemCache({ [firstItem.item_id]: firstItem });
        setCurrentQueueEntry({ itemId: firstItem.item_id, source: "main" });
        setNextCursorToLoad(1);
        setTotalItems(firstItem.total_items);
      } finally {
        if (!isCancelled) {
          setIsInitializing(false);
        }
      }
    }

    void initializeLesson();

    return () => {
      isCancelled = true;
    };
  }, [lessonId]);

  const availableTiles = useMemo(() => {
    if (!currentItem || currentItem.item_type !== "sentence_tiles") {
      return [];
    }
    const remaining = stableShuffle(
      [...currentItem.answer_tiles],
      `${currentItem.item_id}:${currentItem.prompt_text}:sentence-tiles`,
    );
    for (const tile of selectedTiles) {
      const index = remaining.indexOf(tile);
      if (index >= 0) {
        remaining.splice(index, 1);
      }
    }
    return remaining;
  }, [currentItem, selectedTiles]);

  const selectedTileInstances = useMemo(() => buildTileInstances(selectedTiles), [selectedTiles]);
  const availableTileInstances = useMemo(
    () => buildTileInstances(availableTiles),
    [availableTiles],
  );

  const currentAnswer = isMultipleChoiceItem(currentItem)
    ? (selectedOption ?? "")
    : normalizeAnswer(selectedTiles);

  const canCheck =
    currentAnswer.length > 0 && feedback === null && !submitMutation.isPending && !isLessonFinished;

  async function loadNextMainItem() {
    if (totalItems === null || nextCursorToLoad >= totalItems) {
      return null;
    }
    const nextItem = await nextItemMutation.mutateAsync(nextCursorToLoad);
    setItemCache((current) => ({ ...current, [nextItem.item_id]: nextItem }));
    setNextCursorToLoad((cursor) => cursor + 1);
    return { itemId: nextItem.item_id, source: "main" } satisfies QueueEntry;
  }

  async function advanceQueue() {
    setSelectedTiles([]);
    setSelectedOption(null);
    setFeedback(null);

    if (mainQueue.length > 0) {
      const [nextMain, ...remainingMain] = mainQueue;
      setMainQueue(remainingMain);
      if (nextMain) {
        setCurrentQueueEntry(nextMain);
        return;
      }
    }

    const loadedEntry = await loadNextMainItem();
    if (loadedEntry) {
      setCurrentQueueEntry(loadedEntry);
      return;
    }

    if (reviewQueue.length > 0) {
      const [nextReview, ...remainingReview] = reviewQueue;
      setReviewQueue(remainingReview);
      if (nextReview) {
        setCurrentQueueEntry(nextReview);
        return;
      }
    }

    const orderedAnswers = Object.entries(itemCache)
      .sort(([, left], [, right]) => left.order_index - right.order_index)
      .map(([itemId]) => ({
        itemId,
        userAnswer: finalAnswers[itemId],
      }))
      .filter(
        (entry): entry is { itemId: string; userAnswer: string } => entry.userAnswer !== undefined,
      );

    if (orderedAnswers.length !== Object.keys(itemCache).length) {
      throw new Error("Lesson completion attempted before every item had a correct answer.");
    }

    const result = await submitMutation.mutateAsync({
      answers: orderedAnswers,
    });
    setCompletionProgressState(result.progress_state);
    setIsLessonFinished(true);
    setCurrentQueueEntry(null);
    void queryClient.invalidateQueries({ queryKey: pathKeys.all });
    void queryClient.invalidateQueries({ queryKey: unitKeys.all });
  }

  async function handleCheck() {
    if (!currentItem) {
      return;
    }

    const result = await submitMutation.mutateAsync({
      itemId: currentItem.item_id,
      userAnswer: currentAnswer,
    });
    const itemResult = result.item_results[0];
    if (!itemResult) {
      return;
    }

    setFeedback({
      expectedAnswer: itemResult.expected_answer,
      isCorrect: itemResult.is_correct,
      submittedAnswer: itemResult.user_answer,
    });

    if (itemResult.is_correct) {
      setCorrectCount((count) => count + 1);
      setFinalAnswers((current) => ({
        ...current,
        [currentItem.item_id]: itemResult.expected_answer,
      }));
      setCompletedItemIds((current) =>
        current.includes(currentItem.item_id) ? current : [...current, currentItem.item_id],
      );
      return;
    }

    setMistakeCount((count) => count + 1);
    setReviewQueue((current) => [...current, { itemId: currentItem.item_id, source: "review" }]);
  }

  const totalCount = totalItems ?? currentItem?.total_items ?? 1;
  const currentIndex = Math.min(completedItemIds.length + 1, totalCount);
  const remainingReviewCount =
    reviewQueue.length + (currentQueueEntry?.source === "review" ? 1 : 0);
  const submitError = submitMutation.error ? getErrorMessage(submitMutation.error) : null;
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    advanceQueueRef.current = advanceQueue;
    handleCheckRef.current = handleCheck;
  });

  useEffect(() => {
    function handleWindowKeyDown(event: KeyboardEvent) {
      if (event.code !== "Space") {
        return;
      }

      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) {
        return;
      }

      if (isLeaveDialogOpen || isLessonFinished || submitMutation.isPending) {
        return;
      }

      if (feedback) {
        event.preventDefault();
        void advanceQueueRef.current();
        return;
      }

      if (canCheck) {
        event.preventDefault();
        void handleCheckRef.current();
      }
    }

    window.addEventListener("keydown", handleWindowKeyDown);
    return () => {
      window.removeEventListener("keydown", handleWindowKeyDown);
    };
  }, [canCheck, feedback, isLeaveDialogOpen, isLessonFinished, submitMutation.isPending]);

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-[var(--lesson-bg)] font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-stone-900">
        <LessonTopBar
          currentIndex={0}
          onBack={() => setIsLeaveDialogOpen(true)}
          reviewCount={0}
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

  if (isLessonFinished) {
    return (
      <div className="min-h-screen bg-[var(--lesson-bg)] font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-stone-900">
        <LessonTopBar
          currentIndex={totalCount}
          onBack={() => {
            void navigate({ to: "/path" });
          }}
          reviewCount={0}
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
      <div className="min-h-screen bg-[var(--lesson-bg)] px-4 py-8 font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-stone-900 md:px-8">
        <div className="mx-auto max-w-4xl rounded-[1.5rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-8 shadow-[0_12px_30px_rgba(22,28,37,0.05)]">
          Lesson is unavailable.
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--lesson-bg)] pb-12 font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-stone-900">
      <LessonTopBar
        currentIndex={currentIndex}
        onBack={() => setIsLeaveDialogOpen(true)}
        reviewCount={remainingReviewCount}
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
                      selectedOption={selectedOption}
                      setSelectedOption={setSelectedOption}
                    />
                  ) : (
                    <WordBankExercise
                      availableTileInstances={availableTileInstances}
                      feedback={feedback}
                      selectedTileInstances={selectedTileInstances}
                      selectedTiles={selectedTiles}
                      setSelectedTiles={setSelectedTiles}
                    />
                  )}
                </LayoutGroup>
              </div>

              <LessonBottomZone
                canCheck={canCheck}
                feedback={feedback}
                onCheck={() => {
                  void handleCheck();
                }}
                onContinue={() => {
                  void advanceQueue();
                }}
                submitError={submitError}
                submitPending={submitMutation.isPending}
              />
            </div>
          </motion.section>
        </AnimatePresence>
      </main>

      <LeaveLessonDialog
        isOpen={isLeaveDialogOpen}
        onCancel={() => setIsLeaveDialogOpen(false)}
        onConfirm={() => {
          setIsLeaveDialogOpen(false);
          void navigate({ to: "/path" });
        }}
      />
    </div>
  );
}
