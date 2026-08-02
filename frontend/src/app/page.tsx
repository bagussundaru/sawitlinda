"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import { Card, StatCard } from "@/components/Card";
import { ConditionBars, HealthDonut } from "@/components/Charts";
import DronePanel from "@/components/DronePanel";
import InferenceQueue from "@/components/InferenceQueue";
import { LAYERS, layerOf } from "@/lib/severity";
import {
  ApiError,
  getDashboard,
  getResult,
  listMapPoints,
  listResults,
} from "@/lib/api";
import type {
  Dashboard,
  DetectionResult,
  MapPoint,
  ResultListItem,
} from "@/types/detection";

const SpreadMap = dynamic(() => import("@/components/SpreadMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[372px] animate-pulse rounded-[14px] bg-[var(--line-soft)]" />
  ),
});

type LayerKey = "sehat" | "ringan" | "berat";

export default function HomePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [history, setHistory] = useState<ResultListItem[]>([]);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [selected, setSelected] = useState<MapPoint | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [layerOff, setLayerOff] = useState<Record<LayerKey, boolean>>({
    sehat: false,
    ringan: false,
    berat: false,
  });
  const [focus, setFocus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [dashboard, mapPoints, list] = await Promise.all([
          getDashboard(),
          listMapPoints(),
          listResults(),
        ]);
        setData(dashboard);
        setPoints(mapPoints);
        setHistory(list);

        const analyzed = list.find((item) => item.status === "analyzed");
        if (analyzed) setResult(await getResult(analyzed.image_id));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Data gagal dimuat.");
      }
    })();
  }, []);

  // Clicking a point may belong to another image; load that image's result.
  async function selectPoint(point: MapPoint) {
    setSelected(point);
    setHighlighted(point.detection_id);
    if (!result || result.image_id !== point.image_id) {
      try {
        setResult(await getResult(point.image_id));
      } catch {
        /* the panel keeps showing the previous frame */
      }
    }
  }

  const visible = useMemo(
    () =>
      points.filter((point) => {
        if (layerOff[layerOf(point.severity)]) return false;
        if (focus && point.condition !== focus) return false;
        return true;
      }),
    [points, layerOff, focus],
  );

  const layerCounts = useMemo(() => {
    const counts: Record<LayerKey, number> = { sehat: 0, ringan: 0, berat: 0 };
    points.forEach((point) => (counts[layerOf(point.severity)] += 1));
    return counts;
  }, [points]);

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-[12px] border border-[#f0c9c9] bg-[var(--red-bg)] px-4 py-3 text-[12.5px] text-[var(--red)]"
      >
        {error}
      </p>
    );
  }

  if (!data) {
    return <p className="text-sm text-[var(--muted)]">Memuat dashboard…</p>;
  }

  const { summary } = data;
  const share = (n: number) => (summary.total > 0 ? n / summary.total : 0);

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-5">
        <div>
          <div className="text-[11px] font-bold tracking-[0.15em] text-[#5c7a6b]">
            DASHBOARD OPERASIONAL
          </div>
          <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
            Sebaran Kondisi Tanaman
          </h1>
        </div>
        <div className="flex items-center gap-[10px]">
          <span className="mono hidden rounded-[11px] border border-[var(--line)] bg-[var(--card)] px-[14px] py-[10px] text-[11px] text-[var(--muted-3)] sm:block">
            {data.images_analyzed}/{data.images_total} citra dianalisis
          </span>
          <Link
            href="/unggah"
            className="rounded-[11px] bg-[var(--brand)] px-[18px] py-[11px] text-[12.5px] font-bold text-white"
          >
            Unggah &amp; Analisis
          </Link>
        </div>
      </header>

      {data.images_analyzed === 0 && (
        <div className="rounded-[12px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3 text-[12.5px] text-[var(--green-d)]">
          Belum ada citra yang dianalisis.{" "}
          <Link href="/unggah" className="font-bold underline">
            Unggah citra pertama
          </Link>{" "}
          untuk mengisi dashboard ini.
        </div>
      )}

      <section className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
        <StatCard
          label="Total Pohon Terdeteksi"
          value={summary.total}
          share={1}
          note={`${data.images_analyzed} citra`}
        />
        <StatCard
          label="Pohon Sehat"
          value={summary.healthy}
          share={share(summary.healthy)}
          color="var(--healthy)"
        />
        <StatCard
          label="Pohon Bermasalah"
          value={summary.infected}
          share={share(summary.infected)}
          color="var(--mild)"
        />
        <StatCard
          label="Kasus Berat"
          value={summary.severe}
          share={share(summary.severe)}
          color="var(--severe)"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <Card
          title="Peta Perkebunan"
          subtitle="Klik satu titik pohon untuk membuka citra drone & hasil deteksinya"
          action={
            <Link
              href="/peta"
              className="text-[11.5px] font-bold text-[var(--brand-2)]"
            >
              Peta penuh →
            </Link>
          }
        >
          {points.length > 0 ? (
            <>
              <SpreadMap
                points={visible}
                selectedId={selected?.detection_id ?? null}
                onSelect={selectPoint}
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-bold tracking-[0.1em] text-[#83998b]">
                  LAYER
                </span>
                {LAYERS.map((layer) => {
                  const off = layerOff[layer.key];
                  return (
                    <button
                      key={layer.key}
                      onClick={() =>
                        setLayerOff((current) => ({
                          ...current,
                          [layer.key]: !current[layer.key],
                        }))
                      }
                      className="flex items-center gap-2 rounded-[9px] border border-[var(--line)] bg-[#f4f8f5] px-[11px] py-[7px] text-[11px] font-semibold text-[#2c4a39]"
                      style={{
                        textDecoration: off ? "line-through" : "none",
                        opacity: off ? 0.45 : 1,
                      }}
                    >
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: layer.color }}
                      />
                      {layer.label}
                      <span className="mono text-[10px] opacity-65">
                        {layerCounts[layer.key]}
                      </span>
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <p className="text-[12.5px] text-[var(--muted-2)]">
              Belum ada titik berkoordinat. Peta hanya menampilkan pohon dari citra
              yang metadata EXIF-nya memuat GPS.
            </p>
          )}
        </Card>

        <DronePanel
          result={result}
          selected={selected}
          highlighted={highlighted}
          onHighlight={setHighlighted}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <Card title="Distribusi Kondisi Tanaman">
          <ConditionBars
            items={data.by_condition}
            focused={focus}
            onFocus={setFocus}
          />
        </Card>

        <Card title="Rasio Sehat vs Bermasalah">
          <HealthDonut healthy={summary.healthy} affected={summary.infected} />
        </Card>
      </section>

      <section className="grid gap-4">
        <Card title="Antrian Inference" subtitle="Status citra yang masuk ke sistem">
          <InferenceQueue items={history} />
        </Card>
      </section>
    </>
  );
}
