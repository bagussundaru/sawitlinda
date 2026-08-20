"use client";

import type { Evaluation } from "@/types/detection";

/** Metrik yang dibandingkan, beserta arah "lebih baik". Semuanya 0..1. */
const METRICS: { key: keyof Evaluation; label: string }[] = [
  { key: "map50", label: "mAP@50" },
  { key: "micro_precision", label: "Precision" },
  { key: "micro_recall", label: "Recall" },
  { key: "micro_f1", label: "F1" },
];

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function shortDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Batang perbandingan satu metrik antar-run. */
function MetricBars({ runs, metric }: { runs: Evaluation[]; metric: keyof Evaluation }) {
  const values = runs.map((r) => Number(r[metric]) || 0);
  const best = Math.max(...values, 0);

  return (
    <div className="flex flex-col gap-[5px]">
      {runs.map((run, i) => {
        const value = values[i];
        const isBest = best > 0 && value === best;
        return (
          <div key={run.id} className="flex items-center gap-2">
            <span className="mono w-[104px] shrink-0 truncate text-[10.5px] text-[var(--muted-3)]">
              {run.model_name ?? "—"}
            </span>
            <span className="h-[8px] flex-1 overflow-hidden rounded-full bg-[var(--line-soft)]">
              <span
                className="block h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${Math.min(100, value * 100)}%`,
                  background: isBest
                    ? "linear-gradient(90deg,#2FBF71,#0F8A55)"
                    : "var(--mild)",
                }}
              />
            </span>
            <span
              className="mono w-[52px] shrink-0 text-right text-[11px]"
              style={{ fontWeight: isBest ? 700 : 400 }}
            >
              {pct(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Perbandingan antar-model dari evaluasi yang BENAR-BENAR dijalankan.
 *
 * Tidak ada baris yang dibuat sendiri oleh layar ini. Varian model yang belum
 * pernah dilatih dan dievaluasi tidak muncul di sini — menampilkan barisnya
 * dengan angka kosong, apalagi dengan angka karangan, akan membuat tabel ini
 * tidak dapat dipertanggungjawabkan sebagai hasil pengukuran.
 */
export default function ModelComparison({ runs }: { runs: Evaluation[] }) {
  if (runs.length === 0) return null;

  const best = (key: keyof Evaluation) =>
    Math.max(...runs.map((r) => Number(r[key]) || 0), 0);

  return (
    <div className="flex flex-col gap-5">
      {/* --- Tabel --- */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-[12px]">
          <thead>
            <tr className="text-left text-[10.5px] uppercase tracking-[0.07em] text-[var(--muted-3)]">
              <th className="pb-2 pr-3 font-semibold">Model</th>
              <th className="pb-2 pr-3 font-semibold">Dataset</th>
              <th className="pb-2 pr-3 font-semibold">Run</th>
              <th className="pb-2 pr-3 text-right font-semibold">Images</th>
              <th className="pb-2 pr-3 text-right font-semibold">GT</th>
              <th className="pb-2 pr-3 text-right font-semibold">Pred</th>
              {METRICS.map((m) => (
                <th key={String(m.key)} className="pb-2 pr-3 text-right font-semibold">
                  {m.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="border-t border-[var(--line-soft)]">
                <td className="py-[9px] pr-3">
                  <span className="font-semibold text-[var(--ink)]">
                    {run.model_name ?? "—"}
                  </span>
                  {run.inference_mode === "mock" && (
                    <span className="ml-2 rounded-md bg-[var(--red-bg)] px-[6px] py-[1px] text-[10px] font-bold text-[var(--red)]">
                      MOCK
                    </span>
                  )}
                </td>
                <td className="mono py-[9px] pr-3 text-[10.5px] text-[var(--muted)]">
                  {run.source_filename}
                  <br />
                  <span className="text-[var(--muted-3)]">
                    IoU ≥ {run.iou_threshold}
                  </span>
                </td>
                <td className="py-[9px] pr-3 text-[var(--muted)]">
                  {shortDate(run.created_at)}
                </td>
                <td className="mono py-[9px] pr-3 text-right">{run.images}</td>
                <td className="mono py-[9px] pr-3 text-right">{run.ground_truths}</td>
                <td className="mono py-[9px] pr-3 text-right">{run.predictions}</td>
                {METRICS.map((m) => {
                  const value = Number(run[m.key]) || 0;
                  const isBest = runs.length > 1 && value === best(m.key) && value > 0;
                  return (
                    <td
                      key={String(m.key)}
                      className="mono py-[9px] pr-3 text-right"
                      style={{
                        color: isBest ? "var(--brand-2)" : undefined,
                        fontWeight: isBest ? 700 : 400,
                      }}
                    >
                      {pct(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* --- Batang per metrik --- */}
      {runs.length > 1 && (
        <div className="grid gap-5 sm:grid-cols-2">
          {METRICS.map((m) => (
            <div key={String(m.key)} className="flex flex-col gap-2">
              <span className="text-[11.5px] font-bold text-[var(--ink)]">
                {m.label}
              </span>
              <MetricBars runs={runs} metric={m.key} />
            </div>
          ))}
        </div>
      )}

      <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
        Every row is an evaluation that was actually run against ground truth
        annotations — nothing here is generated by this screen. Model variants
        that have not been trained and evaluated yet simply do not appear.
        Comparing rows is only meaningful when they were measured against the
        same dataset at the same IoU threshold, both of which are shown above.
      </p>
    </div>
  );
}
