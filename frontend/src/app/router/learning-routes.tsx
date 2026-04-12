import { createRoute, redirect } from "@tanstack/react-router";

import { refreshKanaOverviewQuery } from "../../features/kana/api/queries";
import { kanjiLessonsQueryOptions } from "../../features/kanji/api/queries";
import { pathQueryOptions } from "../../features/path/api/queries";
import { KanaLessonPage } from "../../pages/kana-lesson-page";
import { KanaPage } from "../../pages/kana-page";
import { KanjiPage } from "../../pages/kanji-page";
import { LessonPage } from "../../pages/lesson-page";
import { PathPage } from "../../pages/path-page";
import { hasAuthToken } from "../../shared/auth/token-store";
import { rootRoute } from "./root-route";

export const pathRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/path",
  component: PathPage,
  beforeLoad: () => {
    if (!hasAuthToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(pathQueryOptions()),
});

export const lessonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/lesson/$lessonId",
  component: LessonPage,
  beforeLoad: () => {
    if (!hasAuthToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(pathQueryOptions()),
});

export const kanjiRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kanji",
  component: KanjiPage,
  beforeLoad: () => {
    if (!hasAuthToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(kanjiLessonsQueryOptions()),
});

export const kanaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kana",
  component: KanaPage,
  beforeLoad: () => {
    if (!hasAuthToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: async ({ context }) => {
    await refreshKanaOverviewQuery(context.queryClient);
  },
});

export const kanaLessonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kana/lesson/$lessonId",
  component: KanaLessonPage,
  beforeLoad: () => {
    if (!hasAuthToken()) {
      throw redirect({ to: "/login" });
    }
  },
});
