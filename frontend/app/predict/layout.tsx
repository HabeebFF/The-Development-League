import BetSlip from "@/components/predict/BetSlip";
import { SlipProvider } from "@/components/predict/slip";

/** Every prediction page shares one bet slip, docked at the bottom. */
export default function PredictLayout({ children }: LayoutProps<"/predict">) {
  return (
    <SlipProvider>
      <div className="pb-20">{children}</div>
      <BetSlip />
    </SlipProvider>
  );
}
