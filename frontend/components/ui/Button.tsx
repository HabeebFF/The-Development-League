import Link from "next/link";
import type { ComponentProps } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "hot";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "btn btn-primary",
  secondary: "btn",
  ghost: "btn btn-ghost",
  hot: "btn btn-hot",
};

/** Class names for an angled button, for places that need them on another element. */
export function buttonClass(variant: ButtonVariant = "secondary", className = ""): string {
  return `${VARIANT[variant]} ${className}`.trim();
}

/** An angled button: primary (gold), secondary (outlined), ghost (quiet) or hot (live red). */
export default function Button({ variant = "secondary", className = "", type = "button", ...rest }: { variant?: ButtonVariant } & ComponentProps<"button">) {
  return <button type={type} {...rest} className={buttonClass(variant, className)} />;
}

/** A link that looks like an angled button. */
export function ButtonLink({ variant = "secondary", className = "", ...rest }: { variant?: ButtonVariant } & ComponentProps<typeof Link>) {
  return <Link {...rest} className={buttonClass(variant, className)} />;
}
