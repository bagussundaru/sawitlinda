"use client";

import { imageFileUrl } from "@/lib/api";
import type { ResultListItem } from "@/types/detection";

function ringkas(item: ResultListItem) {
  if (!item.summary) return null;
  const { total, infected } = item.summary;
  return { total, infected, rasio: total > 0 ? infected / total : 0 };
}

/** Galeri citra yang sudah dianalisis; menggantikan peran peta sebagai pemilih.
 *
 * Pratinjau kecil dengan label pengunggah — itulah cara pengguna mengenali
 * citranya sekarang, sejak koordinat tidak lagi menjadi identitas. */
export default function ImageStrip({
  items,
  selectedId,
  onSelect,
  loading = false,
}: {
  items: ResultListItem[];
  selectedId: string | null;
  onSelect: (item: ResultListItem) => void;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-[10px] sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="kerangka aspect-[4/3]" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-[12.5px] text-[var(--muted-2)]">
        Tidak ada citra yang cocok. Ubah kata pencarian, atau unggah citra baru.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-[10px] sm:grid-cols-3 lg:grid-cols-4">
      {items.map((item, i) => {
        const aktif = item.image_id === selectedId;
        const s = ringkas(item);
        return (
          <button
            key={item.image_id}
            onClick={() => onSelect(item)}
            style={{ ["--i" as string]: i }}
            aria-pressed={aktif}
            className="muncul-skala kartu-tekan group relative overflow-hidden rounded-[13px] border-2 text-left"
            data-aktif={aktif}
          >
            <span
              className="absolute inset-0 rounded-[11px] ring-inset transition"
              style={{
                boxShadow: aktif
                  ? "inset 0 0 0 2px var(--accent)"
                  : "inset 0 0 0 1px var(--line)",
              }}
            />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageFileUrl(item.image_id)}
              alt={item.label ?? item.filename}
              loading="lazy"
              className="aspect-[4/3] w-full object-cover transition duration-300 group-hover:scale-[1.04]"
            />

            <span className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/45 to-transparent px-[9px] pb-[7px] pt-6">
              <span className="block truncate text-[11.5px] font-bold text-white">
                {item.label ?? item.filename}
              </span>
              {s && (
                <span className="mono block text-[10px] text-white/70">
                  {s.total} pohon · {(s.rasio * 100).toFixed(0)}% bermasalah
                </span>
              )}
            </span>

            {s && s.rasio > 0 && (
              <span
                className="pointer-events-none absolute left-0 top-0 h-[3px] rounded-r-full"
                style={{
                  width: `${Math.max(6, s.rasio * 100)}%`,
                  background:
                    s.rasio > 0.35 ? "var(--severe)" : "var(--mild)",
                }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
