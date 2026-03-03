import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: {
    path: "openapi.json",
  },
  output: "src/shared/api/generated",
  plugins: [
    "@hey-api/client-fetch",
    {
      name: "@tanstack/react-query",
      queryOptions: true,
    },
    {
      name: "zod",
    },
  ],
});
