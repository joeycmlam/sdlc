import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import withAuth from "next-auth/middleware";

const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "false";

const authMiddleware = withAuth({
  callbacks: {
    authorized: ({ token }) => !!token,
  },
});

export default function middleware(req: NextRequest) {
  if (!authEnabled) return NextResponse.next();
  return (authMiddleware as unknown as (req: NextRequest) => Response)(req);
}

export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon.ico|auth).*)",
  ],
};
