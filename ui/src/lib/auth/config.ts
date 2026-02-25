/**
 * Auth config. Password hash stored server-side only.
 * Set UI_PASSWORD_HASH in env (e.g. from bcrypt or a precomputed hash).
 * For single-user, a simple SHA-256 hash of the password is acceptable if not exposed.
 */
import crypto from "crypto";

const SESSION_COOKIE = "operator_session";
const SESSION_MAX_AGE = 60 * 60 * 24 * 7; // 7 days
const SESSION_SECRET = process.env.UI_SESSION_SECRET ?? "change-me-in-production";

export const authConfig = {
  SESSION_COOKIE,
  SESSION_MAX_AGE,
  SESSION_SECRET,
  /** Compare password with env UI_PASSWORD_HASH (hex SHA-256). If UI_PASSWORD_HASH not set, any password rejected. */
  checkPassword(password: string): boolean {
    const raw = process.env.UI_PASSWORD_HASH?.trim();
    if (!raw || raw.length !== 64) return false;
    const inputHash = crypto.createHash("sha256").update(password, "utf8").digest("hex");
    try {
      const bufHash = Buffer.from(raw, "hex");
      const bufInput = Buffer.from(inputHash, "hex");
      if (bufHash.length !== 32 || bufInput.length !== 32) return false;
      return crypto.timingSafeEqual(bufHash, bufInput);
    } catch {
      return false;
    }
  },
  /** Create a session token (HMAC of timestamp + random). */
  createToken(): string {
    const payload = `${Date.now()}.${crypto.randomBytes(16).toString("hex")}`;
    const sig = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("hex");
    return `${payload}.${sig}`;
  },
  verifyToken(token: string): boolean {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const [ts, , sig] = parts;
    const expected = crypto.createHmac("sha256", SESSION_SECRET).update(`${parts[0]}.${parts[1]}`).digest("hex");
    if (!crypto.timingSafeEqual(Buffer.from(sig, "hex"), Buffer.from(expected, "hex"))) return false;
    const age = Date.now() - Number(ts);
    return age >= 0 && age < SESSION_MAX_AGE * 1000;
  },
};
