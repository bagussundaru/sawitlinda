"use client";

import { useEffect, useState } from "react";

import ScreenHeading from "@/components/ScreenHeading";
import { ApiError, getDashboard } from "@/lib/api";
import { SEVERITY_COLOR } from "@/lib/severity";
import type { Dashboard, Severity } from "@/types/detection";

const DISEASE_BAR_COLOR = "#BA7517";

function StatCard({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone?: "warn" | "bad";
}) {
  const color =
    tone === "warn"
      ? "var(--amber)"
      : tone === "bad"
        ? "var(--red)"
        : "var(--green-d)";
  return (
    <div className="rounded-[13px] border border-[var(--line)] bg-[var(--card)] p-4">
      <div className="text-[26px] font-bold" style={{ color }}>
        {value}
      </div>
      <div className="mt-[2px] text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Dashboard gagal dimuat.",
        ),
      );
  }, []);

  if (error) {
    return (
      <>
        <ScreenHeading title="Dashboard Ringkasan" />
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
      </>
    );
  }

  if (!data) {
    return <p className="text-sm text-[var(--muted)]">Memuat dashboard…</p>;
  }

  const { summary } = data;
  const maxDisease = Math.max(1, ...data.by_condition.map((d) => d.count));
  const infectedPct =
    summary.total > 0 ? (summary.infected / summary.total) * 100 : 0;

  return (
    <>
      <ScreenHeading
        title="Dashboard Ringkasan"
        subtitle={`Agregat dari ${data.images_analyzed} citra yang dianalisis (dari ${data.images_total} diunggah).`}
      />

      <div className="mb-[22px] grid grid-cols-2 gap-[14px] lg:grid-cols-4">
        <StatCard value={summary.total} label="Total pohon terdeteksi" />
        <StatCard value={summary.healthy} label="Pohon sehat" />
        <StatCard value={summary.infected} label="Bermasalah" tone="warn" />
        <StatCard value={summary.severe} label="Kondisi berat" tone="bad" />
      </div>

      <div className="grid gap-[18px] lg:grid-cols-2">
        <div className="rounded-[13px] border border-[var(--line)] bg-[var(--card)] p-[18px]">
          <h3 className="mb-4 text-sm font-bold">Distribusi kondisi tanaman</h3>
          {data.by_condition.length === 0 ? (
            <p className="text-[12.5px] text-[var(--muted)]">
              Belum ada data. Analisis sebuah citra terlebih dahulu.
            </p>
          ) : (
            data.by_condition.map((item) => (
              <div
                key={item.label}
                className="mb-3 flex items-center gap-[10px] text-[12.5px]"
              >
                <div className="w-[120px] flex-shrink-0">{item.label}</div>
                <div className="h-[22px] flex-1 overflow-hidden rounded-md bg-[var(--page)]">
                  <div
                    className="flex h-full items-center justify-end rounded-md pr-[7px] text-[11px] font-semibold text-white"
                    style={{
                      width: `${Math.max(6, (item.count / maxDisease) * 100)}%`,
                      background:
                        item.label === "Sehat"
                          ? SEVERITY_COLOR.sehat
                          : DISEASE_BAR_COLOR,
                    }}
                  >
                    {item.count}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="rounded-[13px] border border-[var(--line)] bg-[var(--card)] p-[18px]">
          <h3 className="mb-4 text-sm font-bold">Sehat vs bermasalah</h3>
          <div className="flex items-center gap-5">
            <svg width="150" height="150" viewBox="0 0 42 42">
              <circle
                cx="21"
                cy="21"
                r="15.9155"
                fill="none"
                stroke={SEVERITY_COLOR.sehat}
                strokeWidth="6"
              />
              <circle
                cx="21"
                cy="21"
                r="15.9155"
                fill="none"
                stroke={SEVERITY_COLOR.ringan}
                strokeWidth="6"
                strokeDasharray={`${infectedPct} ${100 - infectedPct}`}
                strokeDashoffset="25"
                transform="rotate(-90 21 21)"
              />
              <text
                x="21"
                y="20"
                textAnchor="middle"
                fontSize="7"
                fontWeight="700"
                fill="var(--green)"
              >
                {infectedPct.toFixed(0)}%
              </text>
              <text
                x="21"
                y="27"
                textAnchor="middle"
                fontSize="3.4"
                fill="var(--muted)"
              >
                bermasalah
              </text>
            </svg>
            <div className="text-[12.5px]">
              <div className="mb-2 flex items-center gap-2">
                <i
                  className="h-3 w-3 rounded-[3px]"
                  style={{ background: SEVERITY_COLOR.sehat }}
                />
                Sehat — {summary.healthy} pohon
              </div>
              <div className="mb-2 flex items-center gap-2">
                <i
                  className="h-3 w-3 rounded-[3px]"
                  style={{ background: SEVERITY_COLOR.ringan }}
                />
                Bermasalah — {summary.infected} pohon
              </div>
              <div className="mt-4 space-y-1 text-[11.5px] text-[var(--muted)]">
                {data.by_severity.map((item) => (
                  <div key={item.label} className="flex items-center gap-2">
                    <i
                      className="h-2 w-2 rounded-full"
                      style={{
                        background: SEVERITY_COLOR[item.label as Severity],
                      }}
                    />
                    {item.label}: {item.count}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
