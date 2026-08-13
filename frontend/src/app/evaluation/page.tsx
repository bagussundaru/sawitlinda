"use client";

import { useEffect, useRef, useState } from "react";

import { Card, StatCard } from "@/components/Card";
import { ApiError, listEvaluations, runEvaluation } from "@/lib/api";
import type { Evaluation } from "@/types/detection";

const persen = (v: number) => `${(v * 100).toFixed(1)}%`;

function formatTime(value: string): string {
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/** Peringatan yang harus ikut ke mana pun angka ini dibawa. */
function ModeBanner({ mode, model }: { mode: string; model: string | null }) {
  if (mode === "model") {
    return (
      <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3 text-[12.5px] text-[var(--green-d)]">
        Dievaluasi terhadap model <b>{model}</b>.
      </div>
    );
  }
  return (
    <div className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-4 py-3 text-[12.5px] leading-relaxed text-[var(--amber)]">
      <b>These figures measure MOCK inference, not the model.</b> Detections are
      still generated synthetically, so the metrics below only prove that the
      evaluation pipeline works — do not report them as measurements of
      model.
    </div>
  );
}

function ConfusionMatrix({ data }: { data: Record<string, Record<string, number>> }) {
  const baris = Object.keys(data);
  const kolom = baris.length ? Object.keys(data[baris[0]]) : [];
  const maks = Math.max(
    1,
    ...baris.flatMap((r) => kolom.map((c) => data[r]?.[c] ?? 0)),
  );

  return (
    <div className="overflow-x-auto">
      <table className="text-[11.5px]">
        <thead>
          <tr>
            <th className="p-2 text-left font-semibold text-[var(--muted)]">
              aktual ↓ / prediksi →
            </th>
            {kolom.map((c) => (
              <th key={c} className="p-2 font-semibold text-[var(--muted)]">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {baris.map((r) => (
            <tr key={r}>
              <th className="whitespace-nowrap p-2 text-left font-semibold">{r}</th>
              {kolom.map((c) => {
                const nilai = data[r]?.[c] ?? 0;
                const benar = r === c;
                return (
                  <td
                    key={c}
                    className="p-2 text-center tabular-nums"
                    style={{
                      background: nilai
                        ? benar
                          ? `rgba(47,191,113,${0.12 + 0.5 * (nilai / maks)})`
                          : `rgba(226,87,76,${0.08 + 0.4 * (nilai / maks)})`
                        : "transparent",
                      fontWeight: nilai ? 600 : 400,
                      color: nilai ? "var(--ink)" : "var(--muted-3)",
                    }}
                  >
                    {nilai}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Hasil({ hasil }: { hasil: Evaluation }) {
  return (
    <>
      <ModeBanner mode={hasil.inference_mode} model={hasil.model_name} />

      <section className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
        <StatCard
          label="mAP@50"
          value={Math.round(hasil.map50 * 1000) / 10}
          share={hasil.map50}
          suffix="%"
        />
        <StatCard
          label="Presisi (mikro)"
          value={Math.round(hasil.micro_precision * 1000) / 10}
          share={hasil.micro_precision}
          color="var(--healthy)"
          suffix="%"
        />
        <StatCard
          label="Recall (mikro)"
          value={Math.round(hasil.micro_recall * 1000) / 10}
          share={hasil.micro_recall}
          color="var(--mild)"
          suffix="%"
        />
        <StatCard
          label="F1 (mikro)"
          value={Math.round(hasil.micro_f1 * 1000) / 10}
          share={hasil.micro_f1}
          color="var(--brand-2)"
          suffix="%"
        />
      </section>

      <p className="mono text-[11px] text-[var(--muted-3)]">
        {hasil.source_filename} · IoU ≥ {hasil.iou_threshold} · {hasil.images} images ·{" "}
        {hasil.ground_truths} anotasi acuan · {hasil.predictions} prediksi ·{" "}
        {formatTime(hasil.created_at)}
      </p>

      <Card title="Per-class metrics">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-[12px]">
            <thead>
              <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
                <th className="pb-2 font-semibold">Kelas</th>
                <th className="pb-2 text-right font-semibold">Ground truth</th>
                <th className="pb-2 text-right font-semibold">Prediksi</th>
                <th className="pb-2 text-right font-semibold">TP</th>
                <th className="pb-2 text-right font-semibold">FP</th>
                <th className="pb-2 text-right font-semibold">FN</th>
                <th className="pb-2 text-right font-semibold">Presisi</th>
                <th className="pb-2 text-right font-semibold">Recall</th>
                <th className="pb-2 text-right font-semibold">F1</th>
                <th className="pb-2 text-right font-semibold">AP</th>
              </tr>
            </thead>
            <tbody>
              {hasil.per_class.map((m) => (
                <tr key={m.label} className="border-b border-[var(--line)] last:border-0">
                  <td className="py-[9px] font-semibold">{m.label}</td>
                  <td className="py-[9px] text-right tabular-nums">{m.support}</td>
                  <td className="py-[9px] text-right tabular-nums">{m.predicted}</td>
                  <td className="py-[9px] text-right tabular-nums">{m.true_positive}</td>
                  <td className="py-[9px] text-right tabular-nums text-[var(--mild)]">
                    {m.false_positive}
                  </td>
                  <td className="py-[9px] text-right tabular-nums text-[var(--severe)]">
                    {m.false_negative}
                  </td>
                  <td className="py-[9px] text-right tabular-nums">{persen(m.precision)}</td>
                  <td className="py-[9px] text-right tabular-nums">{persen(m.recall)}</td>
                  <td className="py-[9px] text-right tabular-nums">{persen(m.f1)}</td>
                  <td className="py-[9px] text-right font-semibold tabular-nums">
                    {persen(m.average_precision)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-[var(--muted-3)]">
          mAP@50 is averaged only over classes that have ground truth annotations.
        </p>
      </Card>

      <Card
        title="Confusion matrix"
        subtitle="Hijau di diagonal berarti benar; merah di luar diagonal berarti tertukar kelas"
      >
        <ConfusionMatrix data={hasil.confusion} />
      </Card>
    </>
  );
}

export default function EvaluationPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [iou, setIou] = useState("0.5");
  const [hasil, setHasil] = useState<Evaluation | null>(null);
  const [riwayat, setHistory] = useState<Evaluation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEvaluations()
      .then((list) => {
        setHistory(list);
        if (list.length) setHasil(list[0]);
      })
      .catch(() => setHistory([]));
  }, []);

  async function jalankan() {
    if (!file) {
      setError("Choose an annotation file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const baru = await runEvaluation(file, Number(iou));
      setHasil(baru);
      setHistory((lama) => [baru, ...lama]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <div className="text-[11px] font-bold tracking-[0.15em] text-[#5c7a6b]">
          VALIDASI MODEL
        </div>
        <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
          Evaluation Against Ground Truth
        </h1>
      </header>

      <Card
        title="Upload ground truth annotations"
        subtitle="YOLOv8 export (.zip with labels/ + data.yaml) or COCO JSON — matched by image file name"
      >
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-[6px]">
            <span className="text-[12px] font-semibold text-[var(--muted)]">File</span>
            <button
              onClick={() => inputRef.current?.click()}
              className="rounded-[10px] border border-[var(--line)] bg-white px-4 py-[9px] text-left text-[13px]"
            >
              {file ? file.name : "Choose a .zip or .json…"}
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".zip,.json"
              hidden
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                e.target.value = "";
              }}
            />
          </div>

          <div className="flex flex-col gap-[6px]">
            <span className="text-[12px] font-semibold text-[var(--muted)]">
              Ambang IoU
            </span>
            <input
              type="number"
              min="0.05"
              max="0.95"
              step="0.05"
              value={iou}
              onChange={(e) => setIou(e.target.value)}
              className="w-[110px] rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[13px]"
            />
          </div>

          <button
            onClick={jalankan}
            disabled={busy}
            className="rounded-[11px] bg-[var(--brand)] px-5 py-[11px] text-[13px] font-bold text-white disabled:opacity-60"
          >
            {busy ? "Computing…" : "Run Evaluation"}
          </button>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
          >
            {error}
          </p>
        )}

        <p className="text-[11.5px] leading-relaxed text-[var(--muted-2)]">
          Only images that have annotations are counted. Other images in the system
          are ignored, supaya deteksinya tidak dihitung sebagai positif palsu.
        </p>
      </Card>

      {hasil && <Hasil hasil={hasil} />}

      {riwayat.length > 1 && (
        <Card title="History evaluasi">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-[12px]">
              <thead>
                <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
                  <th className="pb-2 font-semibold">Waktu</th>
                  <th className="pb-2 font-semibold">File</th>
                  <th className="pb-2 font-semibold">Mode</th>
                  <th className="pb-2 text-right font-semibold">IoU</th>
                  <th className="pb-2 text-right font-semibold">mAP@50</th>
                  <th className="pb-2 text-right font-semibold">F1</th>
                </tr>
              </thead>
              <tbody>
                {riwayat.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setHasil(r)}
                    className="cursor-pointer border-b border-[var(--line)] last:border-0 hover:bg-[var(--page)]"
                  >
                    <td className="py-[9px]">{formatTime(r.created_at)}</td>
                    <td className="py-[9px]">{r.source_filename}</td>
                    <td className="py-[9px]">
                      <span
                        className="rounded-md px-[7px] py-[2px] text-[10.5px] font-bold"
                        style={
                          r.inference_mode === "model"
                            ? { background: "var(--green-bg)", color: "var(--green-d)" }
                            : { background: "var(--amber-bg)", color: "var(--amber)" }
                        }
                      >
                        {r.inference_mode}
                      </span>
                    </td>
                    <td className="py-[9px] text-right tabular-nums">{r.iou_threshold}</td>
                    <td className="py-[9px] text-right tabular-nums">{persen(r.map50)}</td>
                    <td className="py-[9px] text-right tabular-nums">{persen(r.micro_f1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
