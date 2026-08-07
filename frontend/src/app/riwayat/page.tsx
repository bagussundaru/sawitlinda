"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, listResults } from "@/lib/api";
import type { ResultListItem } from "@/types/detection";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function RiwayatPage() {
  const [items, setItems] = useState<ResultListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listResults({ limit: 200 })
      .then((halaman) => setItems(halaman.items))
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Riwayat gagal dimuat.",
        ),
      );
  }, []);

  return (
    <>
      <div className="mb-[18px]">
        <h1 className="text-[19px] font-bold">Hasil Deteksi</h1>
        <p className="text-[13px] text-[var(--muted)]">
          Riwayat citra yang pernah diunggah. Klik untuk membuka hasilnya kembali.
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
        <p className="text-sm text-[var(--muted)]">Memuat riwayat…</p>
      )}

      {items?.length === 0 && (
        <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
          Belum ada citra yang diunggah.{" "}
          <Link href="/unggah" className="font-semibold underline">
            Mulai unggah
          </Link>
          .
        </div>
      )}

      <div className="grid gap-[14px] sm:grid-cols-2 lg:grid-cols-3">
        {items?.map((item) => {
          const analyzed = item.status === "analyzed" && item.summary;
          const card = (
            <div className="h-full rounded-[13px] border border-[var(--line)] bg-[var(--card)] p-4 transition hover:border-[var(--green-l)] hover:shadow-[0_6px_18px_rgba(15,110,86,.12)]">
              <div className="truncate text-[13.5px] font-semibold">
                {item.label ?? item.filename}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-[var(--muted)]">
                <span className="mono rounded-md bg-[var(--line-soft)] px-[7px] py-[2px] text-[10.5px] text-[var(--muted-3)]">
                  {item.filename}
                </span>
                <span>{formatDate(item.captured_at ?? item.created_at)}</span>
                {item.gps && (
                  <span className="mono">
                    · {item.gps.lat.toFixed(4)}, {item.gps.lng.toFixed(4)}
                  </span>
                )}
              </div>
              {analyzed && item.summary ? (
                <div className="mt-3 flex gap-3 text-[12px]">
                  <span className="text-[var(--green-d)]">
                    <b>{item.summary.healthy}</b> sehat
                  </span>
                  <span className="text-[var(--amber)]">
                    <b>{item.summary.infected}</b> bermasalah
                  </span>
                  <span className="text-[var(--red)]">
                    <b>{item.summary.severe}</b> berat
                  </span>
                </div>
              ) : (
                <div className="mt-3 text-[12px] text-[var(--muted)]">
                  Belum dianalisis
                </div>
              )}
            </div>
          );

          return analyzed ? (
            <Link key={item.image_id} href={`/hasil/${item.image_id}`}>
              {card}
            </Link>
          ) : (
            <Link
              key={item.image_id}
              href={`/proses?ids=${item.image_id}`}
              title="Jalankan analisis"
            >
              {card}
            </Link>
          );
        })}
      </div>
    </>
  );
}
