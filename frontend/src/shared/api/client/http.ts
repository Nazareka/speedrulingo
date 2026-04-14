import { clearToken, getToken } from "../../auth/token-store";

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

/** Thrown when an authenticated API call returns 401 (expired/invalid bearer token). */
export class SessionExpiredError extends Error {
  override readonly name = "SessionExpiredError";
  constructor(message = "Your session expired. Please sign in again.") {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export function isSessionExpiredError(e: unknown): e is SessionExpiredError {
  return e instanceof SessionExpiredError;
}

/** Result shape from `@hey-api/client-fetch` (`responseStyle: "fields"`, default). */
export type ApiSdkResult<T> = {
  data: T | undefined;
  response: Response;
};

/**
 * How to treat HTTP 401 when `data` is empty:
 * - **`authed`** (default): clear stored token and throw {@link SessionExpiredError} — use for any request that sends `Authorization`.
 * - **`public`**: wrong credentials or similar — throw a generic error and **do not** clear the token (login/register).
 */
export type RequireResponseDataMode = "authed" | "public";

/** Fail fast when the SDK returns no `data` (treat as contract violation or HTTP error). */
export function requireResponseData<T>(
  result: ApiSdkResult<T>,
  mode: RequireResponseDataMode = "authed",
): T {
  const { data, response } = result;
  if (data !== undefined) {
    return data;
  }
  const { status } = response;
  if (status === 401) {
    if (mode === "authed") {
      clearToken();
      throw new SessionExpiredError();
    }
    throw new Error("Invalid email or password.");
  }
  if (status >= 400) {
    throw new Error(`Request failed (${status}).`);
  }
  throw new Error("API response was empty.");
}
