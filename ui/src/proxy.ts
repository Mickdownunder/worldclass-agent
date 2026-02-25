import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "operator_session";

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  // Protect /api except auth
  if (path.startsWith("/api/") && !path.startsWith("/api/auth/")) {
    const token = request.cookies.get(SESSION_COOKIE)?.value;
    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
