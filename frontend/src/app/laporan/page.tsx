"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, exportUrl, listResults } from "@/lib/api";
import type { ResultListItem } from "@/types/detection";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function LaporanPage() {
  const [items, setItems] = useState<ResultListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listResults()
      .then(setItems)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Laporan gagal dimuat."),
      );
  }, []);

  const analyzed = items?.filter((item) => item.status === "analyzed") ?? [];

  return (
    <div className="space-y-[18px]">
      <div>
        <h1 className="text-[19px] font-bold">Laporan</h1>
        <p className="text-[13px] text-[var(--muted)]">
          Unduh hasil analisis per citra dalam format PDF atau CSV.
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
      )}

      {!items && !error && (
        <p className="text-sm text-[var(--muted)]">Memuat laporan…</p>
      )}

      {items && analyzed.length === 0 && (
        <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
          Belum ada citra yang dianalisis.{" "}
          <Link href="/unggah" className="font-semibold underline">
            Unggah citra
          </Link>{" "}
          terlebih dahulu.
        </div>
      )}

      {analyzed.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-[12.5px]">
              <thead>
                <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
                  <th className="pb-2 font-semibold">Berkas</th>
                  <th className="pb-2 font-semibold">Blok</th>
                  <th className="pb-2 font-semibold">Waktu</th>
                  <th className="pb-2 text-right font-semibold">Pohon</th>
                  <th className="pb-2 text-right font-semibold">Bermasalah</th>
                  <th className="pb-2 text-right font-semibold">Berat</th>
                  <th className="pb-2 text-right font-semibold">Unduh</th>
                </tr>
              </thead>
              <tbody>
                {analyzed.map((item) => (
                  <tr
                    key={item.image_id}
                    className="border-b border-[var(--line)] last:border-0"
                  >
                    <td className="py-[10px] font-medium">
                      <Link
                        href={`/hasil/${item.image_id}`}
                        className="hover:text-[var(--green)] hover:underline"
                      >
                        {item.filename}
                      </Link>
                    </td>
                    <td className="py-[10px]">
                      {item.block ? (
                        <span className="rounded-md bg-[var(--green-bg)] px-[7px] py-[2px] text-[11px] font-bold text-[var(--brand)]">
                          {item.block}
                        </span>
                      ) : (
                        <span className="text-[var(--muted-3)]">—</span>
                      )}
                    </td>
                    <td className="py-[10px] text-[var(--muted)]">
                      {formatDate(item.captured_at ?? item.created_at)}
                    </td>
                    <td className="py-[10px] text-right tabular-nums">
                      {item.summary?.total ?? 0}
                    </td>
                    <td
                      className="py-[10px] text-right tabular-nums"
                      style={{ color: "var(--chart-3)" }}
                    >
                      {item.summary?.infected ?? 0}
                    </td>
                    <td
                      className="py-[10px] text-right tabular-nums"
                      style={{ color: "var(--chart-4)" }}
                    >
                      {item.summary?.severe ?? 0}
                    </td>
                    <td className="py-[10px] text-right">
                      <a
                        href={exportUrl(item.image_id, "pdf")}
                        className="mr-3 font-semibold text-[var(--green)] hover:underline"
                      >
                        PDF
                      </a>
                      <a
                        href={exportUrl(item.image_id, "csv")}
                        className="font-semibold text-[var(--green)] hover:underline"
                      >
                        CSV
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
