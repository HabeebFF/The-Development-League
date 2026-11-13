import { redirect } from "next/navigation";

// The shop moved to its own place in the main menu.
export default function Page() {
  redirect("/shop");
}
