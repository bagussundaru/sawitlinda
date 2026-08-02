"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Upload" },
  { href: "/riwayat", label: "Hasil Deteksi" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/peta", label: "Peta Sebaran" },
];

export default function TopBar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b bg-[var(--card)] px-[22px] py-[14px] border-[var(--line)]">
      <Link href="/" className="flex items-center gap-[10px]">
        <span className="flex h-[30px] w-[30px] items-center justify-center rounded-lg bg-[var(--green)] text-base text-white">
          🌴
        </span>
        <span className="text-[17px] font-bold leading-tight text-[var(--green)]">
          SawitScan AI
          <small className="block text-[11px] font-normal text-[var(--muted)]">
            Deteksi penyakit kelapa sawit — citra UAV
          </small>
        </span>
      </Link>

      <nav className="flex flex-wrap gap-1">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`rounded-lg px-[14px] py-2 text-[13.5px] font-medium transition ${
              isActive(link.href)
                ? "bg-[var(--green)] text-white"
                : "text-[var(--muted)] hover:bg-[var(--green-bg)]"
            }`}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
