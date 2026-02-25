import { cookies } from "next/headers";
import { authConfig } from "./config";

export async function getSession(): Promise<boolean> {
  const c = await cookies();
  const token = c.get(authConfig.SESSION_COOKIE)?.value;
  return !!token && authConfig.verifyToken(token);
}

export async function setSession(): Promise<string> {
  const token = authConfig.createToken();
  const c = await cookies();
  c.set(authConfig.SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: authConfig.SESSION_MAX_AGE,
    path: "/",
  });
  return token;
}

export async function clearSession(): Promise<void> {
  const c = await cookies();
  c.delete(authConfig.SESSION_COOKIE);
}
