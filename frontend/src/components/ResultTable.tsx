"use client";

import type { ResultListItem, ResultSort } from "@/types/detection";

export interface UrutanTabel {
  sort: ResultSort;
  order: "asc" | "desc";
}

const KOLOM: { key: ResultSort; label: string; kanan?: boolean }[] = [
  { key: "label", label: "Label" },
  { key: "created_at", label: "Uploaded" },
  { key: "captured_at", label: "Captured" },
  { key: "trees", label: "Trees", kanan: true },
  { key: "affected", label: "Affected", kanan: true },
];

/** Satu definisi lebar kolom, dipakai baris judul dan baris isi. Dua definisi
 *  terpisah akan tergeser satu sama lain begitu salah satunya disunting. */
const GRID =
  "grid grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_minmax(0,1fr)_64px_96px] items-center gap-3";

function tanggal(nilai: string | null): string {
  if (!nilai) return "—";
  return new Date(nilai).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function hari(nilai: string): string {
  return new Date(nilai).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function Panah({ aktif, order }: { aktif: boolean; order: "asc" | "desc" }) {
  return (
    <span
      aria-hidden
      className="inline-block text-[9px] transition-transform duration-200"
      style={{
        opacity: aktif ? 1 : 0.3,
        transform: aktif && order === "asc" ? "rotate(180deg)" : "none",
      }}
    >
      ▼
    </span>
  );
}

/** Riwayat citra sebagai daftar yang dapat diurutkan.
 *
 * Menggantikan galeri pratinjau: galeri memuat setiap berkas citra sekaligus —
 * wajar untuk belasan citra, tidak untuk ribuan. Di sini citra baru diambil
 * setelah satu baris dipilih: satu permintaan, bukan seribu.
 *
 * Disusun dengan grid, bukan elemen <table>: judul kelompok per hari perlu
 * membentang penuh di antara baris, dan di dalam tabel itu memaksa `colSpan`
 * pada baris semu yang tidak punya makna sebagai data.
 */
export default function ResultTable({
  items,
  urutan,
  onUrut,
  selectedId,
  onSelect,
  loading = false,
}: {
  items: ResultListItem[];
  urutan: UrutanTabel;
  onUrut: (kolom: ResultSort) => void;
  selectedId: string | null;
  onSelect: (item: ResultListItem) => void;
  loading?: boolean;
}) {
  // Judul kelompok hanya masuk akal saat daftar terurut waktu; pada urutan lain
  // tanggal yang sama muncul berulang di tempat berbeda dan menyesatkan.
  const kelompokPerHari =
    urutan.sort === "created_at" || urutan.sort === "captured_at";
  const bidangWaktu: "created_at" | "captured_at" =
    urutan.sort === "captured_at" ? "captured_at" : "created_at";

  if (loading) {
    return (
      <div className="flex flex-col gap-[6px]">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="kerangka h-[44px]" />
        ))}
      </div>
    );
  }

  let hariTerakhir: string | null = null;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[620px]">
        {/* Judul kolom */}
        <div
          role="row"
          className={`${GRID} border-b border-[var(--line)] px-[10px] pb-[7px] text-[11px] uppercase tracking-[0.07em] text-[var(--muted-3)]`}
        >
          {KOLOM.map((kolom) => {
            const aktif = urutan.sort === kolom.key;
            return (
              <button
                key={kolom.key}
                onClick={() => onUrut(kolom.key)}
                aria-sort={
                  aktif ? (urutan.order === "asc" ? "ascending" : "descending") : "none"
                }
                className={`inline-flex items-center gap-[5px] font-semibold transition-colors hover:text-[var(--ink)] ${
                  kolom.kanan ? "justify-end" : ""
                }`}
                style={{ color: aktif ? "var(--brand-2)" : undefined }}
              >
                {kolom.label}
                <Panah aktif={aktif} order={urutan.order} />
              </button>
            );
          })}
        </div>

        {items.length === 0 ? (
          <p className="py-8 text-center text-[12.5px] text-[var(--muted-2)]">
            No images match.
          </p>
        ) : (
          items.map((item, i) => {
            const aktif = item.image_id === selectedId;
            const judul = kelompokPerHari
              ? hari(item[bidangWaktu] ?? item.created_at)
              : null;
            const kelompokBaru = judul !== null && judul !== hariTerakhir;
            if (judul !== null) hariTerakhir = judul;

            const s = item.summary;
            const rasio = s && s.total > 0 ? s.infected / s.total : 0;

            return (
              <div key={item.image_id}>
                {kelompokBaru && (
                  <div className="px-[10px] pb-[5px] pt-[13px] text-[10.5px] font-bold uppercase tracking-[0.09em] text-[var(--muted-3)]">
                    {judul}
                  </div>
                )}

                <button
                  onClick={() => onSelect(item)}
                  aria-pressed={aktif}
                  style={{
                    ["--i" as string]: Math.min(i, 12),
                    background: aktif ? "rgba(47,191,113,.10)" : undefined,
                    boxShadow: aktif
                      ? "inset 0 0 0 1px rgba(47,191,113,.45)"
                      : undefined,
                  }}
                  className={`${GRID} muncul w-full rounded-[9px] px-[10px] py-[9px] text-left text-[12.5px] transition hover:bg-[var(--line-soft)]`}
                >
                  <span className="min-w-0">
                    <span
                      className="block truncate font-semibold"
                      style={{ color: aktif ? "var(--brand-2)" : undefined }}
                    >
                      {item.label ?? item.filename}
                    </span>
                    <span className="mono block truncate text-[10.5px] text-[var(--muted-3)]">
                      {item.filename}
                    </span>
                  </span>

                  <span className="text-[var(--muted)]">{tanggal(item.created_at)}</span>
                  <span className="text-[var(--muted)]">{tanggal(item.captured_at)}</span>

                  <span className="mono text-right font-semibold">
                    {s ? s.total : "—"}
                  </span>

                  <span className="flex items-center justify-end gap-2">
                    {s ? (
                      <>
                        <span
                          className="h-[5px] w-[36px] overflow-hidden rounded-full bg-[var(--line-soft)]"
                          aria-hidden
                        >
                          <span
                            className="block h-full rounded-full transition-[width] duration-500"
                            style={{
                              width: `${Math.min(100, rasio * 100)}%`,
                              background:
                                rasio > 0.35 ? "var(--severe)" : "var(--mild)",
                            }}
                          />
                        </span>
                        <span className="mono w-[32px] text-right">
                          {(rasio * 100).toFixed(0)}%
                        </span>
                      </>
                    ) : (
                      <span className="rounded-md bg-[var(--line-soft)] px-[7px] py-[2px] text-[10.5px] text-[var(--muted-3)]">
                        pending
                      </span>
                    )}
                  </span>
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
