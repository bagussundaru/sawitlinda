import type { Metadata } from "next";
import { JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google";

import AppShell from "@/components/AppShell";
import "./globals.css";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SawitScan AI",
  description: "Detection and classification of oil palm plant conditions from UAV imagery",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className={`${sans.variable} ${mono.variable}`}>
      <body style={{ fontFamily: "var(--font-sans), Helvetica, sans-serif" }}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
