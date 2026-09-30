import TeamGate from "./TeamGate";

export default function TeamLayout({ children }: LayoutProps<"/team">) {
  return <TeamGate>{children}</TeamGate>;
}
