"use client";

import { useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, getSystemInfo, runAiReview } from "@/lib/api";
import { SEVERITY_COLOR } from "@/lib/severity";
import type { AiAssessment, DetectionResult } from "@/types/detection";

function formatTime(value: string): string {
  return new Date(value).toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/** Seberapa jauh penilaian model vision meleset dari hasil deteksi. */
function Disagreement({ pp }: { pp: number }) {
  const tinggi = pp >= 20;
  return (
    <div
      className="rounded-[10px] px-3 py-[10px] text-[11.5px] leading-relaxed"
      style={{
        background: tinggi ? "rgba(226,87,76,.08)" : "rgba(47,191,113,.08)",
        color: tinggi ? "#B8362C" : "#0F8A55",
      }}
    >
      {tinggi ? (
        <>
          <b>Selisih {pp} poin persen</b> antara perkiraan model vision dan hasil
          deteksi per pohon. Citra ini layak diperiksa manual.
        </>
      ) : (
        <>
          Selisih dengan hasil deteksi per pohon hanya <b>{pp} poin persen</b> —
          keduanya sepakat.
        </>
      )}
    </div>
  );
}

function Assessment({ ai }: { ai: AiAssessment }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="rounded-full px-[10px] py-[3px] text-[11px] font-bold text-white"
          style={{
            background:
              ai.dominant_condition === "Sehat"
                ? SEVERITY_COLOR.sehat
                : SEVERITY_COLOR.ringan,
          }}
        >
          {ai.dominant_condition}
        </span>
        <span className="mono text-[11px] text-[var(--muted-3)]">
          keyakinan {(ai.confidence * 100).toFixed(0)}% · perkiraan bermasalah{" "}
          {(ai.affected_share * 100).toFixed(0)}%
        </span>
      </div>

      <p className="text-[12.5px] leading-relaxed">{ai.summary}</p>

      {ai.recommendation && (
        <div className="rounded-[10px] bg-[var(--green-bg)] px-3 py-[10px] text-[12px] leading-relaxed text-[var(--green-d)]">
          <b>Saran tindakan:</b> {ai.recommendation}
        </div>
      )}

      {ai.disagreement_pp !== null && <Disagreement pp={ai.disagreement_pp} />}

      {ai.notes.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-[11.5px] text-[var(--muted-2)]">
          {ai.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}

      <p className="mono text-[10.5px] text-[var(--muted-3)]">
        {ai.model} · {formatTime(ai.created_at)}
      </p>
    </>
  );
}

/** Penilaian tingkat citra dari model vision.
 *
 * Sengaja dijalankan atas permintaan, bukan otomatis: panggilannya memakan waktu
 * beberapa detik dan berbiaya, sedangkan deteksi per pohon sudah tersedia. */
export default function AiPanel({
  result,
  onUpdated,
}: {
  result: DetectionResult;
  onUpdated: (updated: DetectionResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function jalankan() {
    setBusy(true);
    setError(null);
    try {
      onUpdated(await runAiReview(result.image_id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        const system = await getSystemInfo().catch(() => null);
        setError(
          system && !system.ai_enabled
            ? "Analisis AI belum dikonfigurasi di server (NEBIUS_API_KEY belum diisi)."
            : err.message,
        );
      } else {
        setError(err instanceof ApiError ? err.message : "Analisis AI gagal.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Analisis AI"
      subtitle="Penilaian keseluruhan citra — pendamping deteksi per pohon, bukan penggantinya"
      action={
        <button
          onClick={jalankan}
          disabled={busy}
          className="rounded-[9px] bg-[var(--brand)] px-4 py-2 text-[12px] font-bold text-white disabled:opacity-60"
        >
          {busy ? "Menganalisis…" : result.ai ? "Ulangi" : "Jalankan"}
        </button>
      }
    >
      {error && (
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
        >
          {error}
        </p>
      )}

      {result.ai ? (
        <Assessment ai={result.ai} />
      ) : (
        !error && (
          <p className="text-[12.5px] text-[var(--muted-2)]">
            Belum ada penilaian untuk citra ini. Klik <b>Jalankan</b> untuk meminta
            model vision membaca citranya dan memberi ringkasan agronomis.
          </p>
        )
      )}
    </Card>
  );
}
