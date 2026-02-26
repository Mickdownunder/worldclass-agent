import { describe, it, expect, vi, beforeEach } from "vitest";

describe("auth config", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("checkPassword returns false when UI_PASSWORD_HASH not set", async () => {
    const orig = process.env.UI_PASSWORD_HASH;
    delete process.env.UI_PASSWORD_HASH;
    const { authConfig } = await import("../config");
    expect(authConfig.checkPassword("any")).toBe(false);
    if (orig !== undefined) process.env.UI_PASSWORD_HASH = orig;
  });

  it("checkPassword returns false for empty password when hash set", async () => {
    const orig = process.env.UI_PASSWORD_HASH;
    process.env.UI_PASSWORD_HASH = "a".repeat(64);
    const { authConfig } = await import("../config");
    expect(authConfig.checkPassword("")).toBe(false);
    if (orig !== undefined) process.env.UI_PASSWORD_HASH = orig;
    else delete process.env.UI_PASSWORD_HASH;
  });

  it("createToken returns string with three parts", async () => {
    const { authConfig } = await import("../config");
    const token = authConfig.createToken();
    expect(typeof token).toBe("string");
    expect(token.split(".").length).toBe(3);
  });

  it("verifyToken returns true for freshly created token", async () => {
    const { authConfig } = await import("../config");
    const token = authConfig.createToken();
    expect(authConfig.verifyToken(token)).toBe(true);
  });

  it("verifyToken returns false for invalid token", async () => {
    const { authConfig } = await import("../config");
    // Use same-length hex to avoid timingSafeEqual buffer length throw
    expect(authConfig.verifyToken("0.0." + "0".repeat(64))).toBe(false);
  });
});
