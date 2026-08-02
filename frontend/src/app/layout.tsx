import type { Metadata } from "next";

import AppShell from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "SawitScan AI",
  description: "Deteksi & klasifikasi kondisi tanaman kelapa sawit dari citra UAV",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
