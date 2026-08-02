"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { getSystemInfo } from "@/lib/api";
import type { SystemInfo } from "@/types/detection";

const NAV = [
  { href: "/", label: "Rumah" },
  { href: "/riwayat", label: "Hasil Deteksi" },
  { href: "/peta", label: "Peta" },
  { href: "/unggah", label: "Unggah" },
  { href: "/laporan", label: "Laporan" },
  { href: "/pengaturan", label: "Pengaturan" },
];

/** Sidebar footer panel. Shows what the system actually runs — a mock-up would
 *  print an mAP here, but quoting a metric for a model that is not loaded would
 *  be inventing a number. */
function ModelPanel({ system }: { system: SystemInfo | null }) {
  const live = system?.model_loaded ?? false;
  return (
    <div className="rounded-[14px] border border-white/10 bg-white/5 p-[14px]">
      <div className="mb-[9px] flex items-center gap-2">
        <span
          className="h-[7px] w-[7px] rounded-full"
          style={{
            background: live ? "var(--accent)" : "var(--mild)",
            boxShadow: `0 0 0 3px ${live ? "rgba(47,191,113,.22)" : "rgba(232,185,59,.22)"}`,
          }}
        />
        <span className="text-[11px] font-bold text-white">
          {live ? "Model aktif" : "Mode mock"}
        </span>
      </div>
      <div className="mono text-[10.5px] leading-[1.7] text-[var(--sidebar-mono)]">
        {system ? (
          live ? (
            <>
              {system.model_name}
              <br />v{system.version} · {system.condition_count} kelas
            </>
          ) : (
            <>
              Model belum dipasang
              <br />v{system.version} · {system.condition_count} kelas
              <br />
              hasil belum representatif
            </>
          )
        ) : (
          "memuat…"
        )}
      </div>
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [system, setSystem] = useState<SystemInfo | null>(null);

  useEffect(() => {
    getSystemInfo()
      .then(setSystem)
      .catch(() => setSystem(null));
  }, []);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="grid min-h-screen lg:grid-cols-[248px_1fr]">
      <aside
        data-open={open}
        className="app-sidebar flex w-[248px] flex-col gap-[34px] bg-[var(--sidebar)] px-[18px] py-[26px] text-[var(--sidebar-ink)]"
      >
        <Link href="/" className="flex items-center gap-[11px] px-[6px]">
          <span
            className="flex h-[34px] w-[34px] items-center justify-center rounded-[11px] text-[15px] font-extrabold text-[#04231a]"
            style={{ background: "linear-gradient(145deg,#2FBF71,#0F8A55)" }}
          >
            S
          </span>
          <span>
            <span className="block text-[16px] font-extrabold tracking-[-0.02em] text-white">
              SawitScan AI
            </span>
            <span className="block text-[10px] font-semibold tracking-[0.16em] text-[var(--sidebar-sub)]">
              UAV PLANT INTEL
            </span>
          </span>
        </Link>

        <nav
          className="flex flex-col gap-1"
          onClick={() => setOpen(false)}
        >
          {NAV.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center justify-between gap-2 rounded-[11px] px-[14px] py-[11px] text-[13px] font-semibold transition"
                style={{
                  background: active ? "rgba(47,191,113,.16)" : "transparent",
                  color: active ? "#fff" : "var(--sidebar-ink)",
                  boxShadow: active ? "inset 0 0 0 1px rgba(47,191,113,.3)" : "none",
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto flex flex-col gap-[14px]">
          <ModelPanel system={system} />
          <span
            title="Autentikasi belum tersedia"
            className="cursor-not-allowed pl-[6px] text-[11.5px] text-[#6fa98d]/60"
          >
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

      <div className="min-w-0">
        <button
          aria-label="Buka menu"
          onClick={() => setOpen(true)}
          className="m-4 rounded-[11px] border border-[var(--line)] bg-[var(--card)] p-[10px] text-[var(--muted)] lg:hidden"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
            <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
          </svg>
        </button>

        <main className="flex min-w-0 flex-col gap-5 px-5 pb-10 pt-2 lg:px-[30px] lg:pt-[26px]">
          {children}
        </main>
      </div>
    </div>
  );
}
