type RouteErrorFallbackProps = {
  error: unknown;
  reset: () => void;
};

export function RouteErrorFallback({ error, reset }: RouteErrorFallbackProps) {
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
