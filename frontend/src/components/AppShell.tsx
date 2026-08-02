"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

type Item = { href: string; label: string; icon: string };

const NAV: Item[] = [
  { href: "/", label: "Rumah", icon: "home" },
  { href: "/riwayat", label: "Hasil Deteksi", icon: "scan" },
  { href: "/peta", label: "Peta", icon: "map" },
  { href: "/unggah", label: "Unggah", icon: "upload" },
  { href: "/laporan", label: "Laporan", icon: "doc" },
];

const FOOTER: Item[] = [{ href: "/pengaturan", label: "Pengaturan", icon: "gear" }];

function Icon({ name }: { name: string }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "home":
      return (
        <svg {...common}>
          <path d="M3 10.5 12 3l9 7.5" />
          <path d="M5 9.5V21h14V9.5" />
        </svg>
      );
    case "scan":
      return (
        <svg {...common}>
          <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    case "map":
      return (
        <svg {...common}>
          <path d="m9 4-6 3v13l6-3 6 3 6-3V4l-6 3z" />
          <path d="M9 4v13M15 7v13" />
        </svg>
      );
    case "upload":
      return (
        <svg {...common}>
          <path d="M12 16V4M8 8l4-4 4 4" />
          <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
      );
    case "doc":
      return (
        <svg {...common}>
          <path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z" />
          <path d="M14 3v4h4M9 13h6M9 17h4" />
        </svg>
      );
    case "gear":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 9 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
        </svg>
      );
    case "logout":
      return (
        <svg {...common}>
          <path d="M15 17l5-5-5-5M20 12H9M12 3H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h7" />
        </svg>
      );
    default:
      return null;
  }
}

function NavLink({ item, active }: { item: Item; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={`flex items-center gap-3 rounded-lg px-3 py-[9px] text-[13.5px] transition ${
        active
          ? "bg-[var(--sidebar-active)] font-semibold text-white"
          : "text-[var(--sidebar-ink)] hover:bg-[var(--sidebar-hover)] hover:text-white"
      }`}
    >
      <Icon name={item.icon} />
      {item.label}
    </Link>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="flex min-h-screen bg-[var(--page)]">
      {/* Sidebar */}
      <aside
        data-open={open}
        className="app-sidebar flex w-[232px] flex-shrink-0 flex-col bg-[var(--sidebar)] px-4 py-5"
      >
        <div className="mb-7 flex items-center gap-[10px] px-2">
          <span className="text-[20px]">🌿</span>
          <span className="text-[16px] font-bold text-white">SawitScan AI</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1" onClick={() => setOpen(false)}>
          {NAV.map((item) => (
            <NavLink key={item.href} item={item} active={isActive(item.href)} />
          ))}
        </nav>

        <div className="flex flex-col gap-1 border-t border-white/10 pt-3">
          {FOOTER.map((item) => (
            <NavLink key={item.href} item={item} active={isActive(item.href)} />
          ))}
          <span
            title="Autentikasi belum tersedia"
            className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-[9px] text-[13.5px] text-[var(--sidebar-ink)]/50"
          >
            <Icon name="logout" />
            Keluar
          </span>
        </div>
      </aside>

      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Konten */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-[var(--line)] bg-[var(--card)] px-5 py-3">
          <button
            aria-label="Buka menu"
            onClick={() => setOpen(true)}
            className="rounded-lg p-2 text-[var(--muted)] hover:bg-[var(--green-bg)] lg:hidden"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
            </svg>
          </button>

          <div className="flex-1" />

          <span className="hidden rounded-full bg-[var(--green-bg)] px-3 py-1 text-[11px] font-semibold text-[var(--green-d)] sm:inline">
            Inference: MOCK
          </span>
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--green-bg)] text-[13px] font-bold text-[var(--green-d)]">
            SS
          </span>
        </header>

        <main className="min-w-0 flex-1 px-5 py-6">{children}</main>
      </div>
    </div>
  );
}
