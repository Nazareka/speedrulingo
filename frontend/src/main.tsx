import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import { configureApiClient } from "./shared/api";
import { env } from "./shared/lib/env";
import "./shared/styles/globals.css";

configureApiClient(env.VITE_API_BASE_URL ?? "/");

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Missing #root element");
}

createRoot(rootElement).render(
  <StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </StrictMode>,
);
