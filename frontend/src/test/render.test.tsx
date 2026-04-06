import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "./test-utils";

describe("renderWithProviders", () => {
  it("wraps with QueryClient and MotionConfig", () => {
    renderWithProviders(<div data-testid="smoke">ok</div>);
    expect(screen.getByTestId("smoke")).toHaveTextContent("ok");
  });
});
