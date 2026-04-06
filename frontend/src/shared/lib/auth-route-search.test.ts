import { describe, expect, it } from "vitest";

import { authRouteSearchSchema } from "./auth-route-search";

describe("authRouteSearchSchema", () => {
  it("parses empty search", () => {
    expect(authRouteSearchSchema.parse({})).toEqual({});
  });

  it("accepts safe in-app redirect", () => {
    expect(authRouteSearchSchema.parse({ redirect: "/account" })).toEqual({
      redirect: "/account",
    });
  });

  it("rejects protocol-relative redirect", () => {
    expect(() => authRouteSearchSchema.parse({ redirect: "//evil.example" })).toThrow();
  });

  it("rejects non-path redirect", () => {
    expect(() => authRouteSearchSchema.parse({ redirect: "https://evil.example" })).toThrow();
  });
});
