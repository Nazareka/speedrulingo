import type { ReactNode } from "react";

const AUTH_PAGE_SURFACE_CLASS =
  "min-h-screen bg-[var(--lesson-bg)] font-['Inter','SF_Pro_Display','SF_Pro_Text','Geist',system-ui,sans-serif] text-[var(--lesson-text)]";

/** Shared chrome for login/register route pages (header + centered column). */
export function AuthPageShell({ children }: { children: ReactNode }) {
  return (
    <div className={AUTH_PAGE_SURFACE_CLASS}>
      <main className="mx-auto max-w-5xl px-4 pt-12 pb-12 md:px-6 md:pt-14">
        <div className="mx-auto w-full max-w-[500px]">
          <header className="mb-7">
            <p className="font-mono text-[11px] text-[var(--lesson-text-faint)] uppercase tracking-[0.35em]">
              SPEEDRULINGO
            </p>
            <p className="mt-2 text-[var(--lesson-text-muted)] text-sm">
              Japanese practice, one unit at a time.
            </p>
          </header>
          {children}
        </div>
      </main>
    </div>
  );
}
