"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import AnnotatedImage from "@/components/AnnotatedImage";
import { Card, StatCard } from "@/components/Card";
import { ConditionBars, HealthDonut } from "@/components/Charts";
import { LEGEND } from "@/lib/severity";
import {
  ApiError,
  getDashboard,
  getResult,
  listMapPoints,
  listResults,
} from "@/lib/api";
import type { Dashboard, DetectionResult, MapPoint } from "@/types/detection";

const SpreadMap = dynamic(() => import("@/components/SpreadMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[280px] animate-pulse rounded-[12px] bg-[var(--page)]" />
  ),
});

export default function HomePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [latest, setLatest] = useState<DetectionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [dashboard, mapPoints, history] = await Promise.all([
          getDashboard(),
          listMapPoints(),
          listResults(),
        ]);
        setData(dashboard);
        setPoints(mapPoints);

        const analyzed = history.find((item) => item.status === "analyzed");
        if (analyzed) setLatest(await getResult(analyzed.image_id));
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Data gagal dimuat.",
        );
      }
    })();
  }, []);

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
      >
        {error}
      </p>
    );
  }

  if (!data) {
    return <p className="text-sm text-[var(--muted)]">Memuat dashboard…</p>;
  }

  const { summary } = data;
  const empty = data.images_analyzed === 0;

  return (
    <div className="space-y-[18px]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[19px] font-bold">Ringkasan Perkebunan</h1>
          <p className="text-[13px] text-[var(--muted)]">
            Agregat dari {data.images_analyzed} citra yang dianalisis, dari{" "}
            {data.images_total} yang diunggah.
          </p>
        </div>
        <Link
          href="/unggah"
          className="rounded-[9px] bg-[var(--green)] px-4 py-[9px] text-[13px] font-semibold text-white hover:bg-[var(--green-d)]"
        >
          + Unggah Citra
        </Link>
      </div>

      {empty && (
        <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
          Belum ada citra yang dianalisis.{" "}
          <Link href="/unggah" className="font-semibold underline">
            Unggah citra pertama
          </Link>{" "}
          untuk mengisi dashboard ini.
        </div>
      )}

      <div className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
        <StatCard value={summary.total} label="Total Pohon Terdeteksi" />
        <StatCard value={summary.healthy} label="Pohon Sehat" tone="good" />
        <StatCard value={summary.infected} label="Pohon Bermasalah" tone="warn" />
        <StatCard value={summary.severe} label="Kasus Berat" tone="bad" />
      </div>

      <div className="grid gap-[18px] xl:grid-cols-[1.35fr_1fr]">
        <Card title="Distribusi Kondisi Tanaman">
          <ConditionBars items={data.by_condition} />
        </Card>
        <Card title="Rasio Sehat vs Bermasalah">
          <HealthDonut healthy={summary.healthy} affected={summary.infected} />
        </Card>
      </div>

      <div className="grid gap-[18px] xl:grid-cols-2">
        <Card
          title="Peta Sebaran"
          action={
            <Link href="/peta" className="text-[12px] font-semibold text-[var(--green)]">
              Buka peta →
            </Link>
          }
        >
          {points.length > 0 ? (
            <>
              <SpreadMap points={points} height={280} />
              <div className="mt-3 flex flex-wrap gap-4 text-[11.5px] text-[var(--muted)]">
                {LEGEND.map((item) => (
                  <span key={item.label} className="flex items-center gap-[6px]">
                    <i
                      className="h-[10px] w-[10px] rounded-full"
                      style={{ background: item.color }}
                    />
                    {item.label}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <p className="text-[12.5px] text-[var(--muted)]">
              Belum ada titik berkoordinat. Peta hanya menampilkan pohon dari citra
              yang metadata EXIF-nya memuat GPS.
            </p>
          )}
        </Card>

        <Card
          title="Citra Drone & Deteksi AI"
          action={
            latest ? (
              <Link
                href={`/hasil/${latest.image_id}`}
                className="text-[12px] font-semibold text-[var(--green)]"
              >
                Lihat detail →
              </Link>
            ) : undefined
          }
        >
          {latest ? (
            <>
              <AnnotatedImage
                imageId={latest.image_id}
                filename={latest.filename}
                detections={latest.detections}
                showLabels={false}
              />
              <p className="mt-3 text-[11.5px] text-[var(--muted)]">
                {latest.filename} · {latest.summary.total} pohon ·{" "}
                {latest.summary.infected} bermasalah
              </p>
            </>
          ) : (
            <p className="text-[12.5px] text-[var(--muted)]">
              Belum ada citra yang dianalisis.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
