import { client } from "./generated/client.gen";

export * from "./generated";
export { authedRequestHeaders, authHeaders, requireResponseData } from "./http";

export function configureApiClient(baseUrl: string): void {
  client.setConfig({ ...client.getConfig(), baseUrl });
}
