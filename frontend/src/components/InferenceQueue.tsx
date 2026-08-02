"use client";

import Link from "next/link";

import type { ResultListItem } from "@/types/detection";

function meta(item: ResultListItem): string {
  const parts: string[] = [];
  if (item.gps) {
    parts.push(`${item.gps.lat.toFixed(4)}, ${item.gps.lng.toFixed(4)}`);
  } else {
    parts.push("GPS tidak ada di EXIF");
  }
  if (item.summary) parts.push(`${item.summary.total} pohon`);
  return parts.join(" · ");
}

/** The redesign's queue list, built from real upload status rather than a
 *  fabricated progress bar: an image is either analysed or still waiting. */
export default function InferenceQueue({ items }: { items: ResultListItem[] }) {
  if (items.length === 0) {
    return (
      <p className="text-[12.5px] text-[var(--muted-2)]">
        Belum ada citra yang diunggah.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {items.slice(0, 8).map((item) => {
        const done = item.status === "analyzed";
        return (
          <div key={item.image_id} className="flex items-center gap-[11px]">
            <span
              className="h-[9px] w-[9px] flex-none rounded-full"
              style={{ background: done ? "var(--accent)" : "var(--muted-3)" }}
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[12.5px] font-semibold">
                {done ? (
                  <Link
                    href={`/hasil/${item.image_id}`}
                    className="hover:underline"
                  >
                    {item.filename}
                  </Link>
                ) : (
                  item.filename
                )}
              </div>
              <div className="mt-[2px] text-[10.5px] text-[#7b917f]">
                {meta(item)}
              </div>
            </div>
            {done ? (
              <span className="mono text-[11px] text-[#4b6656]">selesai</span>
            ) : (
              <Link
                href={`/proses?ids=${item.image_id}`}
                className="mono text-[11px] font-bold text-[var(--brand-2)]"
              >
                analisis →
              </Link>
            )}
          </div>
        );
      })}
    </div>
  );
}
