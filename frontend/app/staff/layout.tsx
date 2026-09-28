import StaffGate from "./StaffGate";

export default function StaffLayout({ children }: LayoutProps<"/staff">) {
  return <StaffGate>{children}</StaffGate>;
}
