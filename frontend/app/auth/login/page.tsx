import type { Metadata } from "next";

import GoogleSignIn from "@/components/auth/GoogleSignIn";
import AuthShell from "@/components/ui/AuthShell";

import LoginForm from "./LoginForm";
import NoAccount from "./NoAccount";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: PageProps<"/auth/login">) {
  const { next } = await searchParams;
  // Only same-site paths: "//evil.test" would leave the site.
  const target = typeof next === "string" && /^\/(?!\/)/.test(next) ? next : null;
  return (
    <AuthShell eyebrow="Welcome back" title="Sign in">
      <LoginForm next={target} />
      <GoogleSignIn next={target} text="signin_with" />
      <NoAccount />
    </AuthShell>
  );
}
