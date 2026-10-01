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
          <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 px-4">
            <Link href="/" className="flex h-14 items-center font-display text-lg tracking-wide uppercase">
              The Development <span className="ml-1.5 text-accent">League</span>
            </Link>
            <div className="-mx-4 flex h-9 flex-1 basis-full sm:basis-auto items-center gap-5 overflow-x-auto px-4 text-sm whitespace-nowrap sm:mx-0 sm:h-14 sm:px-0">
              {[
                ["/standings", "Standings"],
                ["/results", "Results"],
                ["/teams", "Teams"],
              ].map(([href, label]) => (
                <Link key={href} href={href} className="font-medium hover:text-accent">
                  {label}
                </Link>
              ))}
              <span className="flex-1" />
              <Link href="/team" className="text-muted hover:text-text">
                My team
              </Link>
              <Link href="/staff" className="text-muted hover:text-text">
                Staff
              </Link>
            </div>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
