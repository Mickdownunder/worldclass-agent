import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGet = vi.fn();
const mockSet = vi.fn();
const mockDelete = vi.fn();

vi.mock("next/headers", () => ({
  cookies: vi.fn(() =>
    Promise.resolve({
      get: mockGet,
      set: mockSet,
      delete: mockDelete,
    })
  ),
}));

describe("session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getSession", () => {
    it("returns false when no cookie present", async () => {
      mockGet.mockReturnValue(undefined);
      const { getSession } = await import("../session");
      expect(await getSession()).toBe(false);
      expect(mockGet).toHaveBeenCalledWith("operator_session");
    });

    it("returns false when cookie value fails verifyToken", async () => {
      mockGet.mockReturnValue({ value: "0.0." + "0".repeat(64) });
      const { getSession } = await import("../session");
      expect(await getSession()).toBe(false);
    });

    it("returns true when cookie has valid token from createToken", async () => {
      const { authConfig } = await import("../config");
      const validToken = authConfig.createToken();
      mockGet.mockReturnValue({ value: validToken });
      const { getSession } = await import("../session");
      expect(await getSession()).toBe(true);
    });
  });

  describe("setSession", () => {
    it("creates token, sets cookie with correct name and options, returns token", async () => {
      const { setSession } = await import("../session");
      const token = await setSession();
      expect(typeof token).toBe("string");
      expect(token.split(".").length).toBe(3);
      expect(mockSet).toHaveBeenCalledWith(
        "operator_session",
        token,
        expect.objectContaining({
          httpOnly: true,
          sameSite: "lax",
          path: "/",
          maxAge: 60 * 60 * 24 * 7,
        })
      );
      expect(mockSet.mock.calls[0][2].secure).toBe(process.env.NODE_ENV === "production");
    });
  });

  describe("clearSession", () => {
    it("deletes session cookie", async () => {
      const { clearSession } = await import("../session");
      await clearSession();
      expect(mockDelete).toHaveBeenCalledWith("operator_session");
    });
  });
});
