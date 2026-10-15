"use client";

import Link from "next/link";

import { useAuth } from "@/components/Auth";

/** Under the sign-in form: sign up (when open), or how team players get an account. */
export default function NoAccount() {
  const { site } = useAuth();
  return (
    <div className="mt-8 card p-4 text-sm text-muted">
      <p className="font-semibold text-text">No account yet?</p>
      {site.signup && (
        <p className="mt-1">
          <Link href="/auth/signup" className="font-semibold text-accent hover:underline">
            Sign up
          </Link>{" "}
          to play predictions with free coins.
        </p>
      )}
      <p className="mt-1">
        Team players: open the invite link your team manager sent you (it looks like &hellip;/invite/&hellip;) and
        create your account there. Lost it? Ask your manager to copy it again from My team &rarr; Members.
      </p>
    </div>
  );
}
