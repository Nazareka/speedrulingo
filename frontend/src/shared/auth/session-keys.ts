/**
 * React Query key roots for auth-adjacent reads shared across routes (nav, account, path).
 * Keep this module free of queryFn logic — see `session.ts` for loaders.
 */
export const sessionKeys = {
  me: ["session", "me"] as const,
  currentCourse: ["session", "current-course"] as const,
};
