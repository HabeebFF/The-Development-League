import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Inter } from "next/font/google";
import Link from "next/link";

import SiteNav from "@/components/SiteNav";

import "./globals.css";

const body = Inter({ variable: "--font-body", subsets: ["latin"] });
const display = Barlow_Condensed({ variable: "--font-display", weight: ["600", "700", "800"], subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "The Development League", template: "%s | The Development League" },
  description: "The official home of The Development League, a Free Fire esports league.",
};

export const viewport: Viewport = { themeColor: "#07080c", colorScheme: "dark", viewportFit: "cover" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col pb-[var(--bottom-nav-h)] font-sans">
        <SiteNav />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted">
            <span className="font-display text-sm tracking-wide uppercase">
              The Development <span className="text-accent">League</span>
            </span>
            <span className="flex gap-4">
              <Link href="/standings" className="hover:text-white">
                Standings
              </Link>
              <Link href="/results" className="hover:text-white">
                Results
              </Link>
              <Link href="/teams" className="hover:text-white">
                Teams
              </Link>
              <Link href="/staff" className="hover:text-white">
                Staff
              </Link>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
