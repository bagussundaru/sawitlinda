"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import AiPanel from "@/components/AiPanel";
import AnnotatedImage from "@/components/AnnotatedImage";
import { Card, StatCard } from "@/components/Card";
import Legend from "@/components/Legend";
import { ApiError, exportUrl, getResult } from "@/lib/api";
import { SEVERITY_BADGE, SEVERITY_COLOR, isHealthy } from "@/lib/severity";
import type { DetectionResult } from "@/types/detection";

export default function ResultScreen({ imageId }: { imageId: string }) {
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    getResult(imageId)
      .then(setResult)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Hasil tidak dapat dimuat."),
      );
  }, [imageId]);

  if (error) {
    return (
      <>
        <h1 className="mb-3 text-[19px] font-bold">Hasil Deteksi</h1>
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
        <Link
          href="/unggah"
          className="mt-4 inline-block rounded-[9px] bg-[var(--green)] px-4 py-[9px] text-[13px] font-semibold text-white hover:bg-[var(--green-d)]"
        >
          Kembali ke unggah
        </Link>
      </>
    );
  }

  if (!result) {
    return <p className="text-sm text-[var(--muted)]">Memuat hasil…</p>;
  }

  const findings = result.detections.filter((d) => !isHealthy(d.severity));
  const { summary } = result;
  const share = (n: number) => (summary.total > 0 ? n / summary.total : 0);

  return (
    <div className="space-y-[18px]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[19px] font-bold">Hasil Deteksi</h1>
          <p className="text-[13px] text-[var(--muted)]">
            {result.label ? `${result.label} · ` : ""}
            {result.filename} · {summary.total} pohon dianalisis
            {result.gps &&
              ` · ${result.gps.lat.toFixed(5)}, ${result.gps.lng.toFixed(5)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-[10px]">
          <a
            href={exportUrl(imageId, "pdf")}
            className="rounded-[9px] border border-[var(--green-l)] px-4 py-[9px] text-[13px] font-semibold text-[var(--green)] hover:bg-[var(--green-bg)]"
          >
            ⬇ PDF
          </a>
          <a
            href={exportUrl(imageId, "csv")}
            className="rounded-[9px] border border-[var(--green-l)] px-4 py-[9px] text-[13px] font-semibold text-[var(--green)] hover:bg-[var(--green-bg)]"
          >
            ⬇ CSV
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
        <StatCard label="Total Pohon" value={summary.total} share={1} />
        <StatCard
          label="Sehat"
          value={summary.healthy}
          share={share(summary.healthy)}
          color="var(--healthy)"
        />
        <StatCard
          label="Bermasalah"
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
      </div>

      <AiPanel result={result} onUpdated={setResult} />

      <div className="grid gap-[18px] xl:grid-cols-[1.5fr_1fr]">
        <Card title="Citra & Deteksi">
          <AnnotatedImage
            imageId={imageId}
            filename={result.filename}
            detections={result.detections}
            highlighted={hovered}
            onHighlight={setHovered}
          />
          <Legend />
        </Card>

        <Card title={`${findings.length} temuan`}>
          {findings.length === 0 ? (
            <p className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
              Tidak ada pohon bermasalah pada citra ini.
            </p>
          ) : (
            <div className="max-h-[520px] overflow-y-auto pr-1">
              {findings.map((detection, index) => {
                const color = SEVERITY_COLOR[detection.severity];
                const badge = SEVERITY_BADGE[detection.severity];
                const active = hovered === detection.id;
                return (
                  <div
                    key={detection.id}
                    onMouseEnter={() => setHovered(detection.id)}
                    onMouseLeave={() => setHovered(null)}
                    className={`mb-[9px] cursor-pointer rounded-[10px] border border-l-4 border-[var(--line)] bg-[var(--card)] px-[13px] py-[11px] transition ${
                      active
                        ? "outline outline-2 outline-offset-1 outline-[var(--green-l)]"
                        : "hover:shadow-[0_3px_10px_rgba(0,0,0,.05)]"
                    }`}
                    style={{ borderLeftColor: color }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <b className="text-[13px]">{detection.condition}</b>
                      <span
                        className="rounded-full px-2 py-[2px] text-[10px] font-semibold uppercase"
                        style={{ background: badge.bg, color: badge.fg }}
                      >
                        {detection.severity}
                      </span>
                    </div>
                    <div className="text-[11.5px] text-[var(--muted)]">
                      Pohon #{index + 1}
                      {detection.gps &&
                        ` · ${detection.gps.lat.toFixed(5)}, ${detection.gps.lng.toFixed(5)}`}
                      {` · ${(detection.confidence * 100).toFixed(1)}%`}
                    </div>
                    <div className="mt-2 h-[5px] overflow-hidden rounded-full bg-[var(--page)]">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${detection.confidence * 100}%`,
                          background: color,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
