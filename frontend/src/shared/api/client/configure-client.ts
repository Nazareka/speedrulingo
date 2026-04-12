import { client } from "../generated/client.gen";

/** Point the generated `@hey-api` client at the API base URL (called from `main.tsx`). */
export function configureApiClient(baseUrl: string): void {
  client.setConfig({ ...client.getConfig(), baseUrl });
}
