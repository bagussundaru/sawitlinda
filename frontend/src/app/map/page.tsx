"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, listMapPoints, listVillages } from "@/lib/api";
import type { MapImagePoint, VillageInfo } from "@/types/detection";

// Leaflet touches `window` at import time, so it must not run during SSR.
const PlantationMap = dynamic(() => import("@/components/PlantationMap"), {
  ssr: false,
  loading: () => <div className="kerangka h-[460px]" />,
});

const DISTRICT = "Kotawaringin Timur, Central Kalimantan";

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export default function MapPage() {
  const [villages, setVillages] = useState<VillageInfo[]>([]);
  const [points, setPoints] = useState<MapImagePoint[]>([]);
  const [village, setVillage] = useState<string | null>(null);
  const [selected, setSelected] = useState<MapImagePoint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listVillages()
      .then(setVillages)
      .catch(() => setVillages([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listMapPoints(village)
      .then((data) => {
        if (cancelled) return;
        setPoints(data);
        setSelected(null);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Map failed to load.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [village]);

  const withoutCoordinates = points.length === 0 && !loading;

  return (
    <>
      <header className="muncul">
        <div className="text-[11px] font-bold tracking-[0.15em] text-[#5c7a6b]">
          SPATIAL MONITORING
        </div>
        <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
          Plantation Map
        </h1>
        <p className="mt-2 max-w-[620px] text-[13px] text-[var(--muted)]">
          Survey coverage across {DISTRICT}. Each marker is one UAV image,
          coloured by the share of affected trees it contains.
        </p>
      </header>

      {/* --- Village filter --- */}
      <div className="muncul flex flex-wrap items-center gap-2" style={{ ["--i" as string]: 1 }}>
        <span className="text-[11px] font-bold tracking-[0.1em] text-[#83998b]">
          VILLAGE
        </span>
        <div className="flex flex-wrap gap-[6px] rounded-[11px] bg-[#f1f5f2] p-1">
          <button
            onClick={() => setVillage(null)}
            className="rounded-[8px] px-3 py-[7px] text-[11.5px] font-bold transition"
            style={{
              background: village === null ? "var(--brand)" : "transparent",
              color: village === null ? "#fff" : "#5c7a6b",
            }}
          >
            All
          </button>
          {villages.map((v) => (
            <button
              key={v.key}
              onClick={() => setVillage(v.key)}
              title={`${v.district} · ${v.images} images · ${v.trees} trees`}
              className="rounded-[8px] px-3 py-[7px] text-[11.5px] font-bold transition"
              style={{
                background: village === v.key ? "var(--brand)" : "transparent",
                color: village === v.key ? "#fff" : "#5c7a6b",
              }}
            >
              {v.name}
              <span className="mono ml-[6px] text-[10px] opacity-70">{v.images}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="muncul rounded-[12px] border border-[#f0c9c9] bg-[var(--red-bg)] px-4 py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
      )}

      <section className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <div className="muncul" style={{ ["--i" as string]: 2 }}>
          <Card
            title="Survey coverage"
            subtitle={
              loading
                ? "Loading…"
                : `${points.length} geo-referenced image${points.length === 1 ? "" : "s"}`
            }
          >
            <PlantationMap
              points={points}
              villages={villages}
              selectedVillage={village}
              selectedId={selected?.image_id ?? null}
              onSelect={setSelected}
            />

            <div className="flex flex-wrap items-center gap-3 text-[11px] text-[var(--muted)]">
              {[
                { label: "Under 15% affected", color: "var(--healthy)" },
                { label: "15–35% affected", color: "var(--mild)" },
                { label: "Over 35% affected", color: "var(--severe)" },
              ].map((item) => (
                <span key={item.label} className="flex items-center gap-[6px]">
                  <span
                    className="h-[9px] w-[9px] rounded-full"
                    style={{ background: item.color }}
                  />
                  {item.label}
                </span>
              ))}
            </div>

            {withoutCoordinates && (
              <p className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-3 py-[10px] text-[11.5px] leading-relaxed text-[var(--amber)]">
                No image in this selection carries coordinates. The map only
                shows images whose EXIF metadata contains GPS — placing the rest
                at an area centre would look like survey data when it is not.
              </p>
            )}
          </Card>
        </div>

        <div className="muncul flex flex-col gap-4" style={{ ["--i" as string]: 3 }}>
          <Card title="Selected image">
            {selected ? (
              <div className="flex flex-col gap-3">
                <div>
                  <div className="text-[14px] font-bold text-[var(--ink)]">
                    {selected.label ?? selected.filename}
                  </div>
                  <div className="mono text-[10.5px] text-[var(--muted-3)]">
                    {selected.filename}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-[9px]">
                  {[
                    { label: "TREES", value: String(selected.summary.total) },
                    { label: "AFFECTED", value: pct(selected.affected_share) },
                    {
                      label: "SEVERE",
                      value: String(selected.summary.severe),
                    },
                    {
                      label: "DOMINANT",
                      value: selected.dominant_condition ?? "—",
                    },
                  ].map((f) => (
                    <div
                      key={f.label}
                      className="rounded-[11px] bg-[var(--line-soft)] px-3 py-[10px]"
                    >
                      <div className="text-[10px] font-bold tracking-[0.1em] text-[var(--muted-3)]">
                        {f.label}
                      </div>
                      <div className="mt-1 text-[14px] font-bold text-[var(--ink)]">
                        {f.value}
                      </div>
                    </div>
                  ))}
                </div>

                <Link
                  href={`/detections/${selected.image_id}`}
                  className="kartu-tekan rounded-[10px] bg-[var(--brand)] py-[11px] text-center text-[12.5px] font-bold text-white"
                >
                  Open detection result
                </Link>
              </div>
            ) : (
              <p className="text-[12.5px] text-[var(--muted-2)]">
                Click a marker to see its figures.
              </p>
            )}
          </Card>

          <Card title="By village" subtitle={DISTRICT}>
            <div className="flex flex-col gap-[7px]">
              {villages.map((v) => {
                const share = v.trees > 0 ? v.affected / v.trees : 0;
                return (
                  <button
                    key={v.key}
                    onClick={() => setVillage(v.key === village ? null : v.key)}
                    className="kartu-tekan flex items-center justify-between gap-3 rounded-[10px] px-[10px] py-[9px] text-left transition hover:bg-[var(--line-soft)]"
                    style={{
                      background:
                        village === v.key ? "rgba(47,191,113,.10)" : undefined,
                    }}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-[12.5px] font-semibold text-[var(--ink)]">
                        {v.name}
                      </span>
                      <span className="block text-[10.5px] text-[var(--muted-3)]">
                        {v.district}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="mono block text-[12px] font-bold text-[var(--ink)]">
                        {v.images}
                      </span>
                      <span className="mono block text-[10px] text-[var(--muted-3)]">
                        {v.trees > 0 ? `${pct(share)} affected` : "no data"}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
              Villages with no images are still listed — hiding them would read
              as if they were not part of the study.
            </p>
          </Card>
        </div>
      </section>
    </>
  );
}
