import type { QueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KanaLessonItemResponse } from "../../shared/api/generated/types.gen";
import type { FeedbackState } from "../../shared/lesson/session-types";
import { QUICK_TRANSITION } from "../../shared/lesson/ui-constants";
import {
  getKanaAudioBlob,
  prefetchKanaAudioCatalog,
  prefetchKanaAudioForLessonItem,
} from "./audio-cache";
import { refreshKanaOverviewQuery } from "./queries";

/** Let AnimatePresence / feedback transitions finish before auto-playing (see QUICK_TRANSITION). */
export function kanaAutoplayDelayMs(prefersReducedMotion: boolean | null): number {
  if (prefersReducedMotion) {
    return 0;
  }
  return 150 + Math.round(QUICK_TRANSITION.duration * 1000);
}

export function useKanaLessonMountPrefetch(queryClient: QueryClient) {
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const overview = await refreshKanaOverviewQuery(queryClient);
        if (!cancelled) {
          await prefetchKanaAudioCatalog(overview);
        }
      } catch {
        /* Overview may be unavailable; item-level prefetch still covers lesson URLs. */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [queryClient]);
}

export function usePrefetchKanaLessonItemAudio(currentItem: KanaLessonItemResponse | undefined) {
  useEffect(() => {
    if (!currentItem) {
      return;
    }
    void prefetchKanaAudioForLessonItem(currentItem);
  }, [currentItem]);
}

export function useKanaLessonPlayback(currentItem: KanaLessonItemResponse | undefined) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioObjectUrlRef = useRef<string | null>(null);
  const [audioBusy, setAudioBusy] = useState(false);

  const resetAudioPlayback = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioObjectUrlRef.current) {
      URL.revokeObjectURL(audioObjectUrlRef.current);
      audioObjectUrlRef.current = null;
    }
    setAudioBusy(false);
  }, []);

  useEffect(() => {
    return () => {
      resetAudioPlayback();
    };
  }, [resetAudioPlayback]);

  useEffect(() => {
    if (currentItem) {
      resetAudioPlayback();
    }
  }, [currentItem, resetAudioPlayback]);

  const playAudio = useCallback(
    async (audioUrl: string | null | undefined): Promise<void> => {
      if (!audioUrl) {
        return;
      }
      resetAudioPlayback();
      setAudioBusy(true);
      try {
        const blob = await getKanaAudioBlob(audioUrl);
        if (!blob) {
          throw new Error("Kana audio unavailable");
        }
        const objectUrl = URL.createObjectURL(blob);
        audioObjectUrlRef.current = objectUrl;
        const nextAudio = new Audio(objectUrl);
        nextAudio.addEventListener("ended", () => {
          setAudioBusy(false);
        });
        nextAudio.addEventListener("error", () => {
          setAudioBusy(false);
        });
        audioRef.current = nextAudio;
        await nextAudio.play();
      } catch (error) {
        setAudioBusy(false);
        throw error instanceof Error ? error : new Error("Playback failed");
      }
    },
    [resetAudioPlayback],
  );

  return { playAudio, audioBusy };
}

export function useKanaLessonAudioToKanaAutoplay(
  currentItem: KanaLessonItemResponse | undefined,
  feedback: FeedbackState | null,
  playAudio: (url: string | null | undefined) => Promise<void>,
  prefersReducedMotion: boolean | null,
) {
  const playedPromptAudioForItemIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!currentItem || currentItem.item_type !== "audio_to_kana_choice") {
      return;
    }
    if (feedback !== null) {
      return;
    }
    if (playedPromptAudioForItemIdRef.current === currentItem.item_id) {
      return;
    }
    const itemId = currentItem.item_id;
    const url = currentItem.prompt_audio_url;
    const delayMs = kanaAutoplayDelayMs(prefersReducedMotion);
    const timeoutId = window.setTimeout(() => {
      playedPromptAudioForItemIdRef.current = itemId;
      void playAudio(url).catch(() => {
        /* Autoplay failure is non-fatal; user can tap the speaker. */
      });
    }, delayMs);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [currentItem, feedback, playAudio, prefersReducedMotion]);
}

export function useKanaLessonKanaToAudioIncorrectAutoplay(
  feedback: FeedbackState | null,
  currentItem: KanaLessonItemResponse | undefined,
  playAudio: (url: string | null | undefined) => Promise<void>,
  prefersReducedMotion: boolean | null,
) {
  const autoPlayedIncorrectCorrectSoundRef = useRef(false);

  useEffect(() => {
    if (feedback === null) {
      autoPlayedIncorrectCorrectSoundRef.current = false;
      return;
    }
    if (feedback.isCorrect || !currentItem || currentItem.item_type !== "kana_to_audio_choice") {
      return;
    }
    if (autoPlayedIncorrectCorrectSoundRef.current) {
      return;
    }
    const url = currentItem.answer_options.find(
      (option) => option.char === feedback.expectedAnswer,
    )?.audio_url;
    if (!url) {
      return;
    }
    autoPlayedIncorrectCorrectSoundRef.current = true;
    const delayMs = kanaAutoplayDelayMs(prefersReducedMotion);
    const timeoutId = window.setTimeout(() => {
      void playAudio(url).catch(() => {
        /* Autoplay failure is non-fatal; tray offers replay where applicable. */
      });
    }, delayMs);
    return () => {
      window.clearTimeout(timeoutId);
      autoPlayedIncorrectCorrectSoundRef.current = false;
    };
  }, [feedback, currentItem, playAudio, prefersReducedMotion]);
}
