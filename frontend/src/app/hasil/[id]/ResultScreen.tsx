"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Legend from "@/components/Legend";
import ScreenHeading from "@/components/ScreenHeading";
import { ApiError, exportUrl, getResult, imageFileUrl } from "@/lib/api";
import { SEVERITY_BADGE, SEVERITY_COLOR, isHealthy } from "@/lib/severity";
import type { DetectionResult } from "@/types/detection";

export default function ResultScreen({ imageId }: { imageId: string }) {
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    getResult(imageId)
      .then(setResult)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Hasil tidak dapat dimuat.",
        ),
      );
  }, [imageId]);

  if (error) {
    return (
      <>
        <ScreenHeading title="Hasil Deteksi" />
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
        <Link
          href="/"
          className="mt-4 inline-block rounded-[9px] bg-[var(--green)] px-5 py-[10px] text-[13.5px] font-semibold text-white hover:bg-[var(--green-d)]"
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

  return (
    <>
      <ScreenHeading
        title="Hasil Deteksi"
        subtitle={`${result.filename} · ${summary.total} pohon dianalisis, ${summary.infected} terindikasi bermasalah.`}
      />

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <div className="relative overflow-hidden rounded-[14px] border border-[var(--line)] bg-[#2f5a2f]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageFileUrl(imageId)}
              alt={`Citra UAV ${result.filename}`}
              className="block w-full"
              onLoad={(event) =>
                setSize({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
            />
            {size.width > 0 && (
              <svg
                className="absolute inset-0 h-full w-full"
                viewBox={`0 0 ${size.width} ${size.height}`}
                preserveAspectRatio="none"
              >
                {result.detections.map((detection) => {
                  const [x, y, w, h] = detection.bbox;
                  const color = SEVERITY_COLOR[detection.severity];
                  if (isHealthy(detection.severity)) {
                    return (
                      <circle
                        key={detection.id}
                        cx={x + w / 2}
                        cy={y + h / 2}
                        r={Math.max(3, size.width / 200)}
                        fill={color}
                        opacity={0.7}
                      />
                    );
                  }
                  const active = hovered === detection.id;
                  const labelHeight = size.height / 32;
                  return (
                    <g
                      key={detection.id}
                      style={{ cursor: "pointer" }}
                      onMouseEnter={() => setHovered(detection.id)}
                      onMouseLeave={() => setHovered(null)}
                    >
                      <rect
                        x={x}
                        y={y}
                        width={w}
                        height={h}
                        fill="none"
                        stroke={color}
                        strokeWidth={active ? 5 : 2.5}
                        rx={3}
                      />
                      <rect
                        x={x}
                        y={y - labelHeight}
                        width={labelHeight * 2.6}
                        height={labelHeight}
                        fill={color}
                      />
                      <text
                        x={x + labelHeight * 0.25}
                        y={y - labelHeight * 0.25}
                        fill="#fff"
                        fontSize={labelHeight * 0.72}
                        fontFamily="sans-serif"
                      >
                        {(detection.confidence * 100).toFixed(0)}%
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
          </div>

          <Legend />

          <div className="mt-4 flex flex-wrap gap-[10px]">
            <Link
              href="/dashboard"
              className="rounded-[9px] bg-[var(--green)] px-5 py-[10px] text-[13.5px] font-semibold text-white hover:bg-[var(--green-d)]"
            >
              Lihat Dashboard →
            </Link>
            <a
              href={exportUrl(imageId, "pdf")}
              className="rounded-[9px] border border-[var(--green-l)] px-5 py-[10px] text-[13.5px] font-semibold text-[var(--green)]"
            >
              ⬇ Export PDF
            </a>
            <a
              href={exportUrl(imageId, "csv")}
              className="rounded-[9px] border border-[var(--green-l)] px-5 py-[10px] text-[13.5px] font-semibold text-[var(--green)]"
            >
              ⬇ Export CSV
            </a>
          </div>
        </div>

        <div>
          <h3 className="mb-[10px] text-sm font-bold">
            {findings.length} temuan
          </h3>

          {findings.length === 0 ? (
            <p className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
              Tidak ada pohon bermasalah pada citra ini.
            </p>
          ) : (
            <div className="max-h-[560px] overflow-y-auto pr-1">
              {findings.map((detection, index) => {
                const color = SEVERITY_COLOR[detection.severity];
                const badge = SEVERITY_BADGE[detection.severity];
                const active = hovered === detection.id;
                return (
                  <div
                    key={detection.id}
                    onMouseEnter={() => setHovered(detection.id)}
                    onMouseLeave={() => setHovered(null)}
                    className={`mb-[9px] cursor-pointer rounded-[9px] border border-l-4 border-[var(--line)] bg-[var(--card)] px-[13px] py-[11px] transition ${
                      active
                        ? "outline outline-2 outline-offset-1 outline-[var(--green-l)]"
                        : ""
                    }`}
                    style={{ borderLeftColor: color }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <b className="text-[13.5px]">{detection.disease}</b>
                      <span
                        className="rounded-full px-2 py-[2px] text-[10.5px] font-semibold uppercase"
                        style={{ background: badge.bg, color: badge.fg }}
                      >
                        {detection.severity}
                      </span>
                    </div>
                    <div className="text-[11.5px] text-[var(--muted)]">
                      Pohon #{index + 1}
                      {detection.gps &&
                        ` · GPS ${detection.gps.lat.toFixed(5)}, ${detection.gps.lng.toFixed(5)}`}
                      {` · keyakinan ${(detection.confidence * 100).toFixed(1)}%`}
                    </div>
                    <div className="mt-2 h-[5px] overflow-hidden rounded-full bg-[var(--line)]">
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
        </div>
      </div>
    </>
  );
}
