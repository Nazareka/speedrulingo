import type { PropsWithChildren } from "react";

export function PageShell({ children }: PropsWithChildren) {
  return <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 lg:px-8 lg:py-8">{children}</div>;
}
