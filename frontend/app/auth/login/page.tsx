import type { Metadata } from "next";

import LoginForm from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: PageProps<"/auth/login">) {
  const { next } = await searchParams;
  // Only same-site paths: "//evil.test" would leave the site.
  const target = typeof next === "string" && /^\/(?!\/)/.test(next) ? next : null;
  return (
    <section className="mx-auto max-w-sm px-4 py-16">
      <h1 className="font-display text-3xl uppercase">Sign in</h1>
      <LoginForm next={target} />
      <div className="mt-8 rounded-md border border-line p-4 text-sm text-muted">
        <p className="font-semibold text-text">No account yet?</p>
        <p className="mt-1">
          You don&apos;t sign up here. Open the invite link your team manager sent you (it looks like
          &hellip;/invite/&hellip;) and create your account there. Lost it? Ask your manager to copy it
          again from My team &rarr; Members.
        </p>
      </div>
    </section>
  );
}
