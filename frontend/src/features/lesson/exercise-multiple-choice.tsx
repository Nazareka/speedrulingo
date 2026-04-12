import { motion } from "framer-motion";
import { useMemo } from "react";
import type { FeedbackState } from "../../shared/lesson/session-types";
import { LESSON_ANSWER_CONTROL } from "../../shared/lesson/shortcuts";
import { optionTypographyClass } from "../../shared/lesson/typography";
import { FAST_TRANSITION } from "../../shared/lesson/ui-constants";
import { answerStateClasses } from "./answer-styles";
import type { MultipleChoiceLessonItem } from "./item-helpers";
import { buildTileInstances, stableShuffle } from "./tile-helpers";

function multipleChoiceOptionAriaLabel(
  option: string,
  feedback: FeedbackState | null,
  isSelected: boolean,
  expectedAnswer: string,
): string {
  if (!feedback) {
    return isSelected ? `${option}, selected` : option;
  }
  if (option === expectedAnswer) {
    return `${option}, correct`;
  }
  if (isSelected && !feedback.isCorrect) {
    return `${option}, incorrect`;
  }
  return `${option}, not selected`;
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
      {...{ [LESSON_ANSWER_CONTROL]: "" }}
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
      aria-label={multipleChoiceOptionAriaLabel(option, feedback, isSelected, expectedAnswer)}
      className={`w-full rounded-[1.15rem] border px-6 py-[1.35rem] text-left transition duration-150 ${tone}`}
      disabled={disabled}
      initial={false}
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

type MultipleChoiceExerciseProps = {
  currentItem: MultipleChoiceLessonItem;
  feedback: FeedbackState | null;
  selectedOption: string | null;
  selectOption: (option: string) => void;
};

export function MultipleChoiceExercise(props: MultipleChoiceExerciseProps) {
  const { currentItem, feedback, selectedOption, selectOption } = props;
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
          onSelect={() => selectOption(optionInstance.text)}
          option={optionInstance.text}
        />
      ))}
    </div>
  );
}
