"use client";

import Link from "next/link";

import AnnotatedImage from "@/components/AnnotatedImage";
import { exportUrl } from "@/lib/api";
import { SEVERITY_COLOR } from "@/lib/severity";
import type { DetectionResult, MapPoint } from "@/types/detection";

function formatDate(value: string | null | undefined): string {
  if (!value) return "tanpa EXIF";
  return new Date(value).toLocaleDateString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function Fact({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-[11px] bg-white/[.06] px-3 py-[10px]">
      <div className="text-[10px] font-bold tracking-[0.1em] text-[#78a891]">
        {label}
      </div>
      <div
        className="mt-1 text-[14.5px] font-bold text-white"
        style={color ? { color } : undefined}
      >
        {value}
      </div>
    </div>
  );
}

/** The dark panel from the redesign: the selected tree's frame, its facts, and
 *  the export actions. */
export default function DronePanel({
  result,
  selected,
  highlighted,
  onHighlight,
}: {
  result: DetectionResult | null;
  selected: MapPoint | null;
  highlighted: number | null;
  onHighlight: (id: number | null) => void;
}) {
  const detection =
    result && selected
      ? result.detections.find((d) => d.id === selected.detection_id) ?? null
      : null;

  return (
    <div className="flex flex-col gap-[14px] rounded-[18px] bg-[var(--panel-dark)] p-5 text-[var(--panel-dark-ink)]">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[15px] font-extrabold tracking-[-0.02em] text-white">
          Citra Drone &amp; Deteksi AI
        </h3>
        <span className="mono rounded-[7px] bg-white/[.08] px-[9px] py-[5px] text-[10px]">
          {result?.block ? `Blok ${result.block} · ` : ""}
          {selected ? `#${selected.detection_id}` : "—"}
        </span>
      </div>

      {/* Nama berkas. Satu blok berisi banyak bingkai UAV yang saling
          bertumpang tindih dan tampak serupa; tanpa ini tidak ada cara
          membedakan bingkai yang berganti dari bingkai yang tetap. */}
      <div className="-mt-[6px] flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="mono text-[11px] font-bold text-white/85">
          {result?.filename ?? "—"}
        </span>
        {result && (
          <span className="text-[10.5px] text-white/40">
            {result.detections.length} pohon terdeteksi di bingkai ini
          </span>
        )}
      </div>

      {result ? (
        <>
          <AnnotatedImage
            imageId={result.image_id}
            filename={result.filename}
            detections={result.detections}
            highlighted={highlighted}
            onHighlight={onHighlight}
            showLabels={false}
          />

          <div className="grid grid-cols-2 gap-[9px]">
            <Fact
              label="KONDISI"
              value={detection?.condition ?? "Pilih titik di peta"}
            />
            <Fact
              label="KEPARAHAN"
              value={detection?.severity ?? "—"}
              color={detection ? SEVERITY_COLOR[detection.severity] : undefined}
            />
            <Fact
              label="KEYAKINAN"
              value={
                detection ? `${(detection.confidence * 100).toFixed(1)}%` : "—"
              }
            />
            <Fact label="TANGGAL SORTIE" value={formatDate(result.captured_at)} />
          </div>

          <div className="flex gap-2">
            <a
              href={exportUrl(result.image_id, "pdf")}
              className="flex-1 rounded-[11px] bg-[var(--accent)] py-[11px] text-center text-[12px] font-extrabold text-[#05271a]"
            >
              Ekspor PDF
            </a>
            <Link
              href={`/hasil/${result.image_id}`}
              className="flex-1 rounded-[11px] bg-white/[.08] py-[11px] text-center text-[12px] font-bold text-[var(--panel-dark-ink)]"
            >
              Detail citra
            </Link>
          </div>
        </>
      ) : (
        <div className="flex h-[240px] items-center justify-center rounded-[13px] bg-white/[.04] px-6 text-center">
          <p className="mono text-[10.5px] leading-relaxed tracking-[0.08em] text-white/40">
            BELUM ADA CITRA DIANALISIS
          </p>
        </div>
      )}
    </div>
  );
}
