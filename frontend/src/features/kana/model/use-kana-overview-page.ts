import { useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useContinueKanaLearning, useKanaOverviewQuery } from "../api/queries";
import { getKanaAudioBlob, prefetchKanaAudioCatalog } from "./audio-cache";
import {
  buildKanaGroupRows,
  characterProgressPercent,
  isKanaOverviewTileTappable,
  kanaOverviewTileClassName,
  masteryPercent,
} from "./kana-model";

/**
 * Kana overview route: inventory query, continue navigation, and optional tile audio playback.
 */
export function useKanaOverviewPage() {
  const navigate = useNavigate();
  const overviewQuery = useKanaOverviewQuery();
  const continueMutation = useContinueKanaLearning();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioObjectUrlRef = useRef<string | null>(null);
  const [playbackError, setPlaybackError] = useState<string | null>(null);

  const resetAudioPlayback = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioObjectUrlRef.current) {
      URL.revokeObjectURL(audioObjectUrlRef.current);
      audioObjectUrlRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      resetAudioPlayback();
    };
  }, [resetAudioPlayback]);

  useEffect(() => {
    if (!overviewQuery.data) {
      return;
    }
    void prefetchKanaAudioCatalog(overviewQuery.data);
  }, [overviewQuery.data]);

  const playAudio = useCallback(
    async (audioUrl: string | null | undefined) => {
      if (!audioUrl) {
        return;
      }
      setPlaybackError(null);
      resetAudioPlayback();
      try {
        const blob = await getKanaAudioBlob(audioUrl);
        if (!blob) {
          setPlaybackError("Audio file unavailable.");
          return;
        }
        const objectUrl = URL.createObjectURL(blob);
        audioObjectUrlRef.current = objectUrl;
        const nextAudio = new Audio(objectUrl);
        audioRef.current = nextAudio;
        await nextAudio.play();
      } catch {
        setPlaybackError("Could not play audio. Try again.");
      }
    },
    [resetAudioPlayback],
  );

  const handleContinue = useCallback(async () => {
    if (overviewQuery.data?.current_lesson_id) {
      await overviewQuery.refetch();
      await navigate({
        to: "/kana/lesson/$lessonId",
        params: { lessonId: overviewQuery.data.current_lesson_id },
      });
      return;
    }
    const nextLesson = await continueMutation.mutateAsync();
    await overviewQuery.refetch();
    await navigate({
      to: "/kana/lesson/$lessonId",
      params: { lessonId: nextLesson.lesson_id },
    });
  }, [continueMutation, navigate, overviewQuery]);

  const overview = overviewQuery.data;
  const masteredPercent = overview ? masteryPercent(overview) : 0;
  const groupRows = overview ? buildKanaGroupRows(overview) : [];

  return {
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
  };
}

export type KanaOverviewPageModel = ReturnType<typeof useKanaOverviewPage>;
