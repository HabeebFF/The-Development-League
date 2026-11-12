import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Inter } from "next/font/google";

import { AuthGate, AuthProvider } from "@/components/Auth";
import PageTracker from "@/components/PageTracker";
import SiteFooter from "@/components/SiteFooter";
import SiteNav from "@/components/SiteNav";
import RoaringLionIntro from "@/components/league/RoaringLionIntro";
import { INTRO_HEAD_SCRIPT } from "@/components/league/introScript";

import "./globals.css";

const body = Inter({ variable: "--font-body", subsets: ["latin"] });
const display = Barlow_Condensed({ variable: "--font-display", weight: ["600", "700", "800", "900"], subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "The Development League", template: "%s | The Development League" },
  description: "The official home of The Development League, a Free Fire esports league.",
};

export const viewport: Viewport = { themeColor: "#07080c", colorScheme: "dark", viewportFit: "cover" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        {/* Hides the Roaring Lion intro before the first paint once it has played this session. */}
        <script dangerouslySetInnerHTML={{ __html: INTRO_HEAD_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col pb-[var(--bottom-nav-h)] font-sans">
        <AuthProvider>
          <PageTracker />
          <RoaringLionIntro />
          <SiteNav />
          <main className="flex-1">
            <AuthGate>{children}</AuthGate>
          </main>
          <SiteFooter />
        </AuthProvider>
      </body>
    </html>
  );
}
