"use client";

import Link from "next/link";

import AnnotatedImage from "@/components/AnnotatedImage";
import { exportUrl } from "@/lib/api";
import { SEVERITY_COLOR } from "@/lib/severity";
import type { DetectionResult } from "@/types/detection";

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
    <div className="rounded-[11px] bg-white/[.06] px-3 py-[10px] transition-colors">
      <div className="text-[10px] font-bold tracking-[0.1em] text-[#78a891]">
        {label}
      </div>
      <div
        className="angka-halus mt-1 text-[14.5px] font-bold text-white"
        style={color ? { color } : undefined}
      >
        {value}
      </div>
    </div>
  );
}

/** Panel gelap: citra terpilih, kotak deteksinya, dan tindakan ekspor.
 *
 * Pemilihan pohon terjadi di dalam panel ini — mengklik kotak pada citra atau
 * satu baris pada daftar. Sebelumnya pemilihan datang dari peta; sejak konsep
 * bergeser ke pemindaian citra, citra itu sendiri yang menjadi alat pilihnya. */
export default function DronePanel({
  result,
  highlighted,
  onHighlight,
  loading = false,
}: {
  result: DetectionResult | null;
  highlighted: number | null;
  onHighlight: (id: number | null) => void;
  loading?: boolean;
}) {
  const detection =
    result && highlighted !== null
      ? result.detections.find((d) => d.id === highlighted) ?? null
      : null;

  const bermasalah = result
    ? result.detections
        .filter((d) => d.severity !== "sehat")
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 8)
    : [];

  return (
    <div className="flex flex-col gap-[14px] rounded-[18px] bg-[var(--panel-dark)] p-5 text-[var(--panel-dark-ink)]">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[15px] font-extrabold tracking-[-0.02em] text-white">
          Citra &amp; Deteksi AI
        </h3>
        <span className="mono rounded-[7px] bg-white/[.08] px-[9px] py-[5px] text-[10px]">
          {detection ? `#${detection.id}` : "—"}
        </span>
      </div>

      {loading ? (
        <div className="flex h-[240px] flex-col items-center justify-center gap-3 rounded-[13px] bg-white/[.04]">
          <span className="titik-sibuk text-[var(--accent)]">
            <span />
            <span />
            <span />
          </span>
          <span className="mono text-[10.5px] tracking-[0.08em] text-white/40">
            MEMUAT CITRA
          </span>
        </div>
      ) : result ? (
        <>
          {/* Label pengunggah. Identitas citra sekarang ada di sini, bukan pada
              koordinat, jadi ia harus terbaca sebelum apa pun yang lain. */}
          <div className="-mt-[6px] flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-[13px] font-bold text-white">
              {result.label ?? result.filename}
            </span>
            <span className="mono text-[10px] text-white/40">
              {result.filename} · {result.detections.length} pohon
            </span>
          </div>

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
              value={detection?.condition ?? "Pilih pohon pada citra"}
            />
            <Fact
              label="KEPARAHAN"
              value={detection?.severity ?? "—"}
              color={detection ? SEVERITY_COLOR[detection.severity] : undefined}
            />
            <Fact
              label="KEYAKINAN"
              value={detection ? `${(detection.confidence * 100).toFixed(1)}%` : "—"}
            />
            <Fact label="TANGGAL" value={formatDate(result.captured_at)} />
          </div>

          {bermasalah.length > 0 && (
            <div className="flex flex-col gap-[6px]">
              <span className="text-[10px] font-bold tracking-[0.1em] text-[#78a891]">
                PERLU PERHATIAN
              </span>
              <div className="flex flex-wrap gap-[6px]">
                {bermasalah.map((d, i) => (
                  <button
                    key={d.id}
                    onClick={() => onHighlight(highlighted === d.id ? null : d.id)}
                    onMouseEnter={() => onHighlight(d.id)}
                    // Warna keparahan hanya dipakai pada titik penanda, bukan
                    // pada teks: di panel gelap, teks berwarna jenuh sulit dibaca.
                    style={{
                      ["--i" as string]: i,
                      background:
                        highlighted === d.id
                          ? "rgba(47,191,113,.22)"
                          : "rgba(255,255,255,.06)",
                      boxShadow:
                        highlighted === d.id
                          ? "inset 0 0 0 1px rgba(47,191,113,.5)"
                          : "none",
                    }}
                    className="muncul-skala kartu-tekan flex items-center gap-[6px] rounded-[9px] px-[9px] py-[6px] text-[11px] font-semibold"
                  >
                    <span
                      className="h-[7px] w-[7px] shrink-0 rounded-full"
                      style={{ background: SEVERITY_COLOR[d.severity] }}
                    />
                    <span className="text-white/85">{d.condition}</span>
                    <span className="mono text-white/40">
                      {(d.confidence * 100).toFixed(0)}%
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <a
              href={exportUrl(result.image_id, "pdf")}
              className="kartu-tekan flex-1 rounded-[11px] bg-[var(--accent)] py-[11px] text-center text-[12px] font-extrabold text-[#05271a]"
            >
              Ekspor PDF
            </a>
            <Link
              href={`/hasil/${result.image_id}`}
              className="kartu-tekan flex-1 rounded-[11px] bg-white/[.08] py-[11px] text-center text-[12px] font-bold text-[var(--panel-dark-ink)]"
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
