import type { Metadata } from "next";

import AuthShell from "@/components/ui/AuthShell";

import SignupForm from "./SignupForm";

export const metadata: Metadata = { title: "Sign up" };

export default function SignupPage() {
  return (
    <AuthShell eyebrow="Join the league" title="Sign up">
      <SignupForm />
    </AuthShell>
  );
}
