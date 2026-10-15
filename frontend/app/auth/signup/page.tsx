import type { Metadata } from "next";

import SignupForm from "./SignupForm";

export const metadata: Metadata = { title: "Sign up" };

export default function SignupPage() {
  return (
    <section className="mx-auto max-w-sm px-4 py-16">
      <h1 className="font-display text-3xl uppercase">Sign up</h1>
      <SignupForm />
    </section>
  );
}
