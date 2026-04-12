import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { BookOpen, Home, LogOut, Shapes, User } from "lucide-react";
import { useEffect } from "react";

import { useMeQuery } from "../../shared/auth/session";
import { clearToken, hasAuthToken } from "../../shared/auth/token-store";
import { PageShell } from "../../shared/ui/layout/page-shell";

/**
 * Authenticated app chrome: top nav, active-route styling, and lesson/auth full-bleed passthrough.
 */
export function AppFrame() {
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
    if (!hasAuthToken() || !meQuery.error) {
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
