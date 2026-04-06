/** Presence attribute for exercise controls where focus often stays on a `<button>` after click; Space may still mean “Check”. */
export const LESSON_ANSWER_CONTROL = "data-lesson-answer-control";

export function isLessonAnswerControlTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) {
    return false;
  }
  return target.closest(`[${LESSON_ANSWER_CONTROL}]`) !== null;
}

/** Avoid stealing Space from native activation on buttons, links, and similar controls. */
export function isSpaceTargetInsideInteractiveControl(target: EventTarget | null): boolean {
  if (!(target instanceof Node)) {
    return false;
  }
  const element = target instanceof Element ? target : target.parentElement;
  if (!element) {
    return false;
  }
  if (element instanceof HTMLElement && element.isContentEditable) {
    return true;
  }
  return (
    element.closest(
      [
        "button",
        "a[href]",
        "input",
        "textarea",
        "select",
        "option",
        "summary",
        '[role="button"]',
        '[role="link"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[role="option"]',
        '[role="switch"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="combobox"]',
        '[role="slider"]',
      ].join(", "),
    ) !== null
  );
}
