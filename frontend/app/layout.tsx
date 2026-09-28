import type { Metadata, Viewport } from "next";
import { Anton, Inter } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const body = Inter({ variable: "--font-body", subsets: ["latin"] });
const display = Anton({ variable: "--font-display", weight: "400", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "The Development League", template: "%s | The Development League" },
  description: "The official home of The Development League, a Free Fire esports league.",
};

export const viewport: Viewport = { themeColor: "#0b0b0f", colorScheme: "dark" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="sticky top-0 z-20 border-b border-line bg-bg/90 backdrop-blur">
          <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
            <Link href="/" className="font-display text-lg tracking-wide uppercase">
              The Development <span className="text-accent">League</span>
            </Link>
            <Link href="/staff" className="text-sm text-muted hover:text-text">
              Staff
            </Link>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
