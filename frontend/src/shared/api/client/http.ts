import { getToken } from "../../auth/token-store";

/** Attach `Authorization: Bearer` when a token is present. */
export function authHeaders(token?: string): Record<string, string> | undefined {
  if (!token) {
    return undefined;
  }
  return { Authorization: `Bearer ${token}` };
}

/** Headers for authenticated requests using the current stored token. */
export function authedRequestHeaders(): Record<string, string> | undefined {
  return authHeaders(getToken());
}

/** Fail fast when the SDK returns no `data` (treat as contract violation). */
export function requireResponseData<T>(data: T | undefined): T {
  if (data === undefined) {
    throw new Error("API response was empty.");
  }
  return data;
}
