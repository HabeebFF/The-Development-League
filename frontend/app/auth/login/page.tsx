import type { Metadata } from "next";

import LoginForm from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: PageProps<"/auth/login">) {
  const { next } = await searchParams;
  const target = typeof next === "string" && next.startsWith("/") ? next : "/staff";
  return (
    <section className="mx-auto max-w-sm px-4 py-16">
      <h1 className="font-display text-3xl uppercase">Sign in</h1>
      <LoginForm next={target} />
    </section>
  );
}
