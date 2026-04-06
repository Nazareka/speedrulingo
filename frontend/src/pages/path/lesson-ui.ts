import type { LucideIcon } from "lucide-react";
import { BookOpen, GraduationCap, ScrollText } from "lucide-react";

import type { LessonSummary } from "../../shared/api/generated/types.gen";

/** API `kind` field — still `string` at rest, but named at call sites for clarity. */
type LessonKindFromApi = LessonSummary["kind"];
/** API `state` field — same. */
type LessonStateFromApi = LessonSummary["state"];

/** Kinds we style explicitly; unknown API kinds fall back to `normal` styling. */
type KnownLessonKind = "normal" | "review_previous_units" | "exam";

export type LessonKindUi = {
  label: string;
  Icon: LucideIcon;
  incompleteCircleClass: string;
  completedHex: string;
  lightFillHex: string;
  nextHighlightClass: string;
};

const LESSON_KIND_UI: Record<KnownLessonKind, LessonKindUi> = {
  normal: {
    label: "Lesson",
    Icon: BookOpen,
    incompleteCircleClass: "border-[#bfdbfe] bg-[#eff6ff] text-[#1d4ed8]",
    completedHex: "#2563eb",
    lightFillHex: "#eff6ff",
    nextHighlightClass:
      "z-[1] shadow-[inset_0_0_0_2px_rgba(37,99,235,0.4),inset_0_2px_16px_rgba(37,99,235,0.2)]",
  },
  review_previous_units: {
    label: "Review",
    Icon: ScrollText,
    incompleteCircleClass: "border-amber-200 bg-amber-50 text-amber-800",
    completedHex: "#f59e0b",
    lightFillHex: "#fffbeb",
    nextHighlightClass:
      "z-[1] shadow-[inset_0_0_0_2px_rgba(245,158,11,0.45),inset_0_2px_16px_rgba(245,158,11,0.22)]",
  },
  exam: {
    label: "Exam",
    Icon: GraduationCap,
    incompleteCircleClass: "border-rose-200 bg-rose-50 text-rose-900",
    completedHex: "#e11d48",
    lightFillHex: "#fff1f2",
    nextHighlightClass:
      "z-[1] shadow-[inset_0_0_0_2px_rgba(225,29,72,0.4),inset_0_2px_16px_rgba(225,29,72,0.18)]",
  },
};

function isKnownLessonKind(kind: LessonKindFromApi): kind is KnownLessonKind {
  return kind === "normal" || kind === "review_previous_units" || kind === "exam";
}

function fallbackKindLabel(kind: string): string {
  return kind.replaceAll("_", " ");
}

/** Resolved UI for a lesson kind, including fallbacks for unknown API values. */
export function getLessonKindUi(kind: LessonKindFromApi): LessonKindUi {
  if (isKnownLessonKind(kind)) {
    return LESSON_KIND_UI[kind];
  }
  return {
    ...LESSON_KIND_UI.normal,
    label: fallbackKindLabel(kind),
  };
}

type KnownLessonState = "completed" | "in_progress" | "not_started";

const LESSON_STATE_LABEL: Record<KnownLessonState, string> = {
  completed: "Completed",
  in_progress: "In progress",
  not_started: "Not started",
};

function isKnownLessonState(state: LessonStateFromApi): state is KnownLessonState {
  return state === "completed" || state === "in_progress" || state === "not_started";
}

export function getLessonStateLabel(state: LessonStateFromApi): string {
  if (isKnownLessonState(state)) {
    return LESSON_STATE_LABEL[state];
  }
  return state;
}
