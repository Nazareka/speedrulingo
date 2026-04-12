import { useQueryClient } from "@tanstack/react-query";
import { useReducedMotion } from "framer-motion";
import { useCallback, useState } from "react";

import {
  useKanaLessonAudioToKanaAutoplay,
  useKanaLessonKanaToAudioIncorrectAutoplay,
  useKanaLessonMountPrefetch,
  useKanaLessonPlayback,
  usePrefetchKanaLessonItemAudio,
} from "./use-kana-lesson-page-audio";
import { useKanaLessonSession } from "./use-kana-lesson-session";

/**
 * Route-level orchestration for the kana lesson: session, audio prefetch/playback, and playback error UX.
 */
export function useKanaLessonPage(lessonId: string) {
  const queryClient = useQueryClient();
  const prefersReducedMotion = useReducedMotion();
  const session = useKanaLessonSession(lessonId);

  useKanaLessonMountPrefetch(queryClient);
  const { playAudio, audioBusy } = useKanaLessonPlayback(session.currentItem);
  usePrefetchKanaLessonItemAudio(session.currentItem);
  useKanaLessonAudioToKanaAutoplay(
    session.currentItem,
    session.feedback,
    playAudio,
    prefersReducedMotion,
  );
  useKanaLessonKanaToAudioIncorrectAutoplay(
    session.feedback,
    session.currentItem,
    playAudio,
    prefersReducedMotion,
  );

  const [audioPlaybackError, setAudioPlaybackError] = useState<string | null>(null);

  const playAudioWithError = useCallback(
    async (url: string | null | undefined) => {
      setAudioPlaybackError(null);
      try {
        await playAudio(url);
      } catch {
        setAudioPlaybackError("Could not play audio. Try again or check your connection.");
      }
    },
    [playAudio],
  );

  return {
    ...session,
    audioBusy,
    audioPlaybackError,
    playAudioWithError,
    prefersReducedMotion,
  };
}

export type KanaLessonPageModel = ReturnType<typeof useKanaLessonPage>;
