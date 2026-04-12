import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Link,
  Outlet,
  RouterProvider,
  redirect,
  useRouterState,
} from "@tanstack/react-router";
import { BookOpen, Home, LogOut, Shapes, User } from "lucide-react";
import { useEffect } from "react";
import { refreshKanaOverviewQuery } from "../features/kana/queries";
import { kanjiLessonsQueryOptions } from "../features/kanji/queries";
import { pathQueryOptions } from "../features/path/queries";
import { AccountPage } from "../pages/account-page";
import { KanaLessonPage } from "../pages/kana-lesson-page";
import { KanaPage } from "../pages/kana-page";
import { KanjiPage } from "../pages/kanji-page";
import { LessonPage } from "../pages/lesson";
import { LoginPage } from "../pages/login-page";
import { PathPage } from "../pages/path/page";
import { RegisterPage } from "../pages/register-page";
import { currentCourseQueryOptions, meQueryOptions, useMeQuery } from "../shared/auth/session";
import { clearToken, getToken } from "../shared/auth/token-store";
import { authRouteSearchSchema } from "../shared/lib/auth-route-search";
import { queryClient } from "../shared/lib/query-client";
import { PageShell } from "../shared/ui/layout/page-shell";

function hasToken(): boolean {
  return getToken().length > 0;
}

function RouteErrorFallback({ error, reset }: { error: unknown; reset: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="mx-auto max-w-lg px-6 py-16 text-center">
      <p className="font-semibold text-[var(--lesson-text)] text-lg">Something went wrong</p>
      <p className="mt-2 text-[var(--lesson-text-muted)] text-sm">{message}</p>
      <button
        className="mt-6 rounded-full border border-[var(--lesson-border)] px-4 py-2 text-[var(--lesson-text)] text-sm"
        onClick={() => reset()}
        type="button"
      >
        Try again
      </button>
    </div>
  );
}

function AppFrame() {
  const meQuery = useMeQuery();
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const isLessonMode = pathname.startsWith("/lesson/") || pathname.startsWith("/kana/lesson/");
  const isAuthMode = pathname === "/login" || pathname === "/register";
  const isPathActive = pathname === "/path";
  const isKanaActive = pathname === "/kana";
  const isKanjiActive = pathname === "/kanji";
  const isAccountActive = pathname === "/account";

  const navLinkBase =
    "inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--lesson-accent)]";
  const navPathActive =
    "border-[var(--lesson-accent)] bg-[var(--lesson-accent)] text-white hover:bg-[var(--lesson-accent-hover)]";
  const navKanjiActive =
    "border-[var(--lesson-accent)] bg-[var(--lesson-accent-soft)] text-[var(--lesson-accent)] hover:bg-[var(--lesson-accent-soft)]";
  const navKanji =
    "border-[var(--lesson-border-soft)] bg-[var(--lesson-surface)] text-[var(--lesson-text-muted)] hover:bg-[var(--lesson-surface-muted)]";
  const navAccountActive =
    "border-[var(--lesson-border-hover)] bg-[var(--lesson-surface-muted)] text-[var(--lesson-text-muted)] hover:bg-[var(--lesson-surface-muted)]";
  const navAccount =
    "border-[var(--lesson-border-soft)] bg-[var(--lesson-surface)] text-[var(--lesson-text-soft)] hover:bg-[var(--lesson-surface-muted)]";
  const navLogout =
    "border-[var(--lesson-border-soft)] bg-[var(--lesson-surface)] text-[var(--lesson-text-muted)] hover:bg-[var(--lesson-surface-muted)]";

  useEffect(() => {
    if (!hasToken() || !meQuery.error) {
      return;
    }
    clearToken();
    const path = window.location.pathname;
    if (path !== "/login" && path !== "/register") {
      window.location.replace("/login");
    }
  }, [meQuery.error]);

  if (isLessonMode || isAuthMode) {
    return <Outlet />;
  }

  return (
    <PageShell>
      <div className="rounded-[1.6rem] border border-[var(--lesson-border)] bg-[var(--lesson-bg)]">
        <div className="flex items-center justify-between border-[var(--lesson-border-soft)] border-b p-3 md:p-4">
          <p className="min-w-0 font-mono text-[14px] text-[var(--lesson-text-faint)] uppercase tracking-[0.28em]">
            SPEEDRULINGO
          </p>

          <nav className="flex items-center gap-2">
            <Link
              className={`${navLinkBase} ${isPathActive ? navPathActive : navKanji}`}
              to="/path"
            >
              <Home aria-hidden="true" className="h-4 w-4" />
              <span className={isPathActive ? "font-semibold" : ""}>Path</span>
            </Link>

            <Link
              className={`${navLinkBase} ${isKanaActive ? navKanjiActive : navKanji}`}
              to="/kana"
            >
              <Shapes aria-hidden="true" className="h-4 w-4" />
              <span className={isKanaActive ? "font-semibold" : ""}>Kana</span>
            </Link>

            <Link
              className={`${navLinkBase} ${isKanjiActive ? navKanjiActive : navKanji}`}
              to="/kanji"
            >
              <BookOpen aria-hidden="true" className="h-4 w-4" />
              <span className={isKanjiActive ? "font-semibold" : ""}>Kanji</span>
            </Link>

            <Link
              className={`${navLinkBase} ${isAccountActive ? navAccountActive : navAccount}`}
              to="/account"
            >
              <User aria-hidden="true" className="h-4 w-4" />
              <span className={isAccountActive ? "font-semibold" : ""}>Account</span>
            </Link>

            {meQuery.data ? (
              <button
                className={`${navLinkBase} ${navLogout}`}
                onClick={() => {
                  clearToken();
                  window.location.href = "/login";
                }}
                type="button"
              >
                <LogOut aria-hidden="true" className="h-4 w-4" />
                <span className="whitespace-nowrap">Log out</span>
              </button>
            ) : null}
          </nav>
        </div>

        <Outlet />
      </div>
    </PageShell>
  );
}

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: AppFrame,
  errorComponent: RouteErrorFallback,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: hasToken() ? "/path" : "/login" });
  },
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
  validateSearch: (raw) => authRouteSearchSchema.parse(raw),
});

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/register",
  component: RegisterPage,
  validateSearch: (raw) => authRouteSearchSchema.parse(raw),
});

const pathRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/path",
  component: PathPage,
  beforeLoad: () => {
    if (!hasToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(pathQueryOptions()),
});

const lessonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/lesson/$lessonId",
  component: LessonPage,
  beforeLoad: () => {
    if (!hasToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(pathQueryOptions()),
});

const kanjiRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kanji",
  component: KanjiPage,
  beforeLoad: () => {
    if (!hasToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) => context.queryClient.ensureQueryData(kanjiLessonsQueryOptions()),
});

const kanaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kana",
  component: KanaPage,
  beforeLoad: () => {
    if (!hasToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: async ({ context }) => {
    // Fresh overview when landing on /kana (e.g. after /kana/lesson/…); fetchQuery updates cache directly.
    await refreshKanaOverviewQuery(context.queryClient);
  },
});

const kanaLessonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kana/lesson/$lessonId",
  component: KanaLessonPage,
  beforeLoad: () => {
    if (!hasToken()) {
      throw redirect({ to: "/login" });
    }
  },
});

const accountRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/account",
  component: AccountPage,
  beforeLoad: () => {
    if (!hasToken()) {
      throw redirect({ to: "/login" });
    }
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(meQueryOptions(true)),
      context.queryClient.ensureQueryData(currentCourseQueryOptions(true)),
    ]),
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  pathRoute,
  lessonRoute,
  kanaRoute,
  kanaLessonRoute,
  kanjiRoute,
  accountRoute,
]);

const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  context: { queryClient },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function AppRouter() {
  return <RouterProvider router={router} context={{ queryClient }} />;
}
