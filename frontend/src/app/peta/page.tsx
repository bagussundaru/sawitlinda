"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import Legend from "@/components/Legend";
import ScreenHeading from "@/components/ScreenHeading";
import { ApiError, listMapPoints } from "@/lib/api";
import type { MapPoint } from "@/types/detection";

// Leaflet touches `window` on import, so it must never run during SSR.
const SpreadMap = dynamic(() => import("@/components/SpreadMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[420px] animate-pulse rounded-[14px] bg-[var(--line)]" />
  ),
});

export default function PetaPage() {
  const [points, setPoints] = useState<MapPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMapPoints()
      .then(setPoints)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Peta gagal dimuat."),
      );
  }, []);

  return (
    <>
      <ScreenHeading
        title="Peta Sebaran"
        subtitle="Titik pohon diplot berdasarkan koordinat GPS dari metadata citra UAV."
      />

      {error && (
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
      )}

      {!points && !error && (
        <p className="text-sm text-[var(--muted)]">Memuat peta…</p>
      )}

      {points && points.length === 0 && (
        <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
          Belum ada titik untuk dipetakan. Peta hanya menampilkan pohon dari
          citra yang metadatanya memuat koordinat GPS.
        </div>
      )}

      {points && points.length > 0 && (
        <>
          <SpreadMap points={points} />
          <Legend filled />
          <div className="mt-[10px] flex items-center gap-[6px] text-xs text-[var(--muted)]">
            📍 Klik titik untuk melihat detail pohon.
          </div>
        </>
      )}
    </>
  );
}
