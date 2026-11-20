"use client";

import Link from "next/link";

import { useAuth } from "../Auth";
import { SkeletonRows } from "../league/Loading";
import NewTeam from "./NewTeam";

/** The /create-team page: sign in first, then the form (or the team that's waiting). */
export default function CreateTeam() {
  const { status } = useAuth();
  if (status === "loading") return <SkeletonRows count={4} />;
  if (status !== "in") {
    return (
      <div className="card p-4 text-sm">
        <p className="font-display text-lg uppercase">Sign in first</p>
        <p className="mt-1 text-muted">The account that creates the team becomes its manager.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link href="/auth/signup?next=/create-team" className="btn btn-primary px-4 py-1.5 text-xs">
            Create an account
          </Link>
          <Link href="/auth/login?next=/create-team" className="btn px-4 py-1.5 text-xs">
            Sign in
          </Link>
        </div>
      </div>
    );
  }
  return <NewTeam />;
}
