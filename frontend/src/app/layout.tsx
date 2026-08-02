import type { Metadata } from "next";

import TopBar from "@/components/TopBar";
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
        <div className="mx-auto min-h-screen max-w-[1080px] bg-[var(--page)]">
          <TopBar />
          <main className="screen px-[22px] pb-[60px] pt-[26px]">{children}</main>
        </div>
      </body>
    </html>
  );
}
