import { client } from "./generated/client.gen";

export * from "./generated";

export function configureApiClient(baseUrl: string): void {
  client.setConfig({ ...client.getConfig(), baseUrl });
}

export function authHeaders(token?: string): Record<string, string> | undefined {
  if (!token) {
    return undefined;
  }
  return { Authorization: `Bearer ${token}` };
}
