import { authedRequestHeaders } from "../../../shared/api";
import type {
  KanaLessonItemResponse,
  KanaOverviewResponse,
} from "../../../shared/api/generated/types.gen";

const PREFETCH_CONCURRENCY = 6;

const blobByNormalizedUrl = new Map<string, Blob>();
const inFlightByKey = new Map<string, Promise<Blob | null>>();

export function normalizeKanaAudioUrl(url: string): string {
  if (typeof window === "undefined") {
    return url;
  }
  try {
    return new URL(url, window.location.origin).href;
  } catch {
    return url;
  }
}

function uniqueUrls(urls: ReadonlyArray<string | null | undefined>): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of urls) {
    if (!raw) {
      continue;
    }
    const key = normalizeKanaAudioUrl(raw);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(key);
  }
  return out;
}

/**
 * Returns cached MP3 (etc.) for this asset URL, or fetches once with auth headers and caches in memory.
 */
export async function getKanaAudioBlob(url: string): Promise<Blob | null> {
  const key = normalizeKanaAudioUrl(url);
  const cached = blobByNormalizedUrl.get(key);
  if (cached) {
    return cached;
  }
  let pending = inFlightByKey.get(key);
  if (pending === undefined) {
    pending = (async () => {
      try {
        const requestHeaders = authedRequestHeaders();
        const response = await fetch(key, {
          ...(requestHeaders ? { headers: requestHeaders } : {}),
        });
        if (!response.ok) {
          return null;
        }
        const blob = await response.blob();
        blobByNormalizedUrl.set(key, blob);
        return blob;
      } catch {
        return null;
      } finally {
        inFlightByKey.delete(key);
      }
    })();
    inFlightByKey.set(key, pending);
  }
  return pending;
}

function chunkUrls(urls: string[], chunkSize: number): string[][] {
  const out: string[][] = [];
  for (let index = 0; index < urls.length; index += chunkSize) {
    out.push(urls.slice(index, index + chunkSize));
  }
  return out;
}

/** Prefetch every character audio from the kana overview (typically while the user is on /kana). */
export async function prefetchKanaAudioCatalog(overview: KanaOverviewResponse): Promise<void> {
  const urls = uniqueUrls(
    overview.scripts.flatMap((scriptGroup) =>
      scriptGroup.characters.map((character) => character.audio_url),
    ),
  );
  for (const batch of chunkUrls(urls, PREFETCH_CONCURRENCY)) {
    // Sequential batches: each batch runs up to PREFETCH_CONCURRENCY requests in parallel.
    // biome-ignore lint/performance/noAwaitInLoops: intentional batching to cap concurrent network requests
    await Promise.all(batch.map((url) => getKanaAudioBlob(url)));
  }
}

export function collectLessonItemAudioUrls(item: KanaLessonItemResponse): string[] {
  const raw: Array<string | null | undefined> = [item.prompt_audio_url];
  for (const option of item.answer_options) {
    raw.push(option.audio_url);
  }
  return uniqueUrls(raw);
}

/** Ensures audio for the current lesson item is cached (no-op if already in catalog cache). */
export async function prefetchKanaAudioForLessonItem(item: KanaLessonItemResponse): Promise<void> {
  const urls = collectLessonItemAudioUrls(item);
  await Promise.all(urls.map((url) => getKanaAudioBlob(url)));
}
