"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Card } from "@/components/Card";
import TrainingChart from "@/components/TrainingChart";
import {
  ApiError,
  activateModel,
  getTrainingConfig,
  getTrainingStatus,
  listTrainingRuns,
  startTraining,
} from "@/lib/api";
import type {
  TrainingConfig,
  TrainingRun,
  TrainingStatus,
} from "@/types/detection";

const JEDA_POLLING_MS = 2500;

const WARNA_STATUS: Record<string, { bg: string; fg: string; label: string }> = {
  queued: { bg: "var(--line-soft)", fg: "var(--muted)", label: "Queued" },
  running: { bg: "rgba(232,185,59,.16)", fg: "var(--amber)", label: "Running" },
  done: { bg: "rgba(47,191,113,.14)", fg: "var(--brand-2)", label: "Done" },
  failed: { bg: "var(--red-bg)", fg: "var(--red)", label: "Failed" },
};

function Lencana({ status }: { status: string }) {
  const w = WARNA_STATUS[status] ?? WARNA_STATUS.queued;
  return (
    <span
      className="rounded-full px-[10px] py-[3px] text-[11px] font-bold"
      style={{ background: w.bg, color: w.fg }}
    >
      {w.label}
    </span>
  );
}

function persen(nilai: number | null | undefined) {
  return typeof nilai === "number" ? `${(nilai * 100).toFixed(1)}%` : "—";
}

export default function TrainingPage() {
  const [config, setConfig] = useState<TrainingConfig | null>(null);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [aktifJob, setActiveJob] = useState<string | null>(null);
  const [status, setStatus] = useState<TrainingStatus | null>(null);

  const [dataset, setDataset] = useState<File | null>(null);
  const [epochs, setEpochs] = useState("50");
  const [baseModel, setBaseModel] = useState("yolov8m.pt");
  const [runName, setRunName] = useState("");

  const [busy, setBusy] = useState(false);
  const [mengaktifkan, setMengaktifkan] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pesan, setPesan] = useState<string | null>(null);

  const muatRuns = useCallback(() => {
    listTrainingRuns()
      .then((daftar) => {
        setRuns(daftar);
        // Sambungkan kembali ke training yang masih berjalan setelah halaman
        // dimuat ulang — tanpa ini, progres seolah hilang saat refresh.
        setActiveJob((sekarang) => {
          if (sekarang) return sekarang;
          const berjalan = daftar.find(
            (r) => r.status === "running" || r.status === "queued",
          );
          return berjalan?.job_id ?? null;
        });
      })
      .catch(() => setRuns([]));
  }, []);

  useEffect(() => {
    getTrainingConfig()
      .then(setConfig)
      .catch(() => setConfig(null));
    muatRuns();
  }, [muatRuns]);

  // --- Polling progres ---
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!aktifJob) return;
    let dibatalkan = false;

    async function tanya() {
      try {
        const s = await getTrainingStatus(aktifJob as string);
        if (dibatalkan) return;
        setStatus(s);
        if (s.status === "done" || s.status === "failed") {
          muatRuns();
          return; // berhenti bertanya
        }
      } catch {
        // Kegagalan sesaat tidak menghentikan pemantauan: mesin Modal bisa
        // sedang menyalakan container dan belum menjawab.
      }
      if (!dibatalkan) timer.current = setTimeout(tanya, JEDA_POLLING_MS);
    }

    tanya();
    return () => {
      dibatalkan = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [aktifJob, muatRuns]);

  async function mulai(e: React.FormEvent) {
    e.preventDefault();
    if (!dataset) return;
    setBusy(true);
    setError(null);
    setPesan(null);
    setStatus(null);
    try {
      const run = await startTraining(dataset, Number(epochs), baseModel, runName);
      setActiveJob(run.job_id);
      setPesan(`Training "${run.run_name}" started.`);
      muatRuns();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start training.");
    } finally {
      setBusy(false);
    }
  }

  async function aktifkan(jobId: string) {
    setMengaktifkan(true);
    setError(null);
    setPesan(null);
    try {
      const run = await activateModel(jobId);
      setPesan(
        `Model "${run.run_name}" is now used for every following analysis.`,
      );
      muatRuns();
      getTrainingConfig().then(setConfig).catch(() => {});
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not set the active model.",
      );
    } finally {
      setMengaktifkan(false);
    }
  }

  const berjalan = status?.status === "running" || status?.status === "queued";
  const total = status?.total_epochs ?? Number(epochs);
  const kemajuan = total ? Math.min(100, ((status?.epoch ?? 0) / total) * 100) : 0;

  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-[22px] font-extrabold tracking-[-0.02em] text-[var(--ink)]">
          Model Training
        </h1>
        <p className="text-[13px] text-[var(--muted)]">
          Retrain the detection model on a GPU machine, then make it the model
          the application uses.
        </p>
      </header>

      {config && !config.configured && (
        <div className="rounded-[12px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-4 py-3 text-[12.5px] leading-relaxed text-[var(--amber)]">
          <b>Training engine is not configured.</b> Set{" "}
          <code className="mono">MODAL_TRAINING_URL</code> dan{" "}
          <code className="mono">MODAL_TRAINING_TOKEN</code> on the server, then
          restart the backend. See{" "}
          <code className="mono">docs/TRAINING.md</code>.
        </div>
      )}

      {/* --- Formulir --- */}
      <Card
        title="Start new training"
        subtitle="Dataset in YOLOv8 format (.zip) containing data.yaml plus train/valid folders"
      >
        <form onSubmit={mulai} className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[260px] flex-1 flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Dataset file
              </span>
              <input
                type="file"
                accept=".zip,application/zip"
                onChange={(e) => setDataset(e.target.files?.[0] ?? null)}
                className="rounded-[10px] border border-dashed border-[var(--line)] bg-white px-3 py-[9px] text-[12px] file:mr-3 file:rounded-[7px] file:border-0 file:bg-[var(--line-soft)] file:px-3 file:py-[5px] file:text-[11.5px] file:font-semibold"
              />
            </label>

            <label className="flex w-[130px] flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Epochs
              </span>
              <input
                type="number"
                min={1}
                max={config?.max_epochs ?? 300}
                value={epochs}
                onChange={(e) => setEpochs(e.target.value)}
                className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
              />
            </label>

            <label className="flex w-[160px] flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Base model
              </span>
              <select
                value={baseModel}
                onChange={(e) => setBaseModel(e.target.value)}
                className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
              >
                {(config?.base_models ?? ["yolov8m.pt"]).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex min-w-[190px] flex-1 flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Version name (optional)
              </span>
              <input
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                placeholder="mis. sawit-v2"
                className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[12px] outline-none focus:border-[var(--accent)]"
              />
            </label>

            <button
              type="submit"
              disabled={busy || !dataset || berjalan || !config?.configured}
              className="rounded-[10px] bg-[var(--brand)] px-5 py-[11px] text-[12.5px] font-bold text-white disabled:opacity-50"
            >
              {busy ? "Uploading…" : "Start Training"}
            </button>
          </div>

          <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
            Training runs on a GPU and <b>costs money per use</b>.
            The dataset is sent to the training engine once, then the process runs
            there — this page may be closed, progress is still recorded.
            {config ? ` Dataset size limit ${config.max_dataset_mb} MB.` : ""}
          </p>
        </form>

        {pesan && (
          <p className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-3 py-[10px] text-[12px] text-[var(--green-d)]">
            {pesan}
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
          >
            {error}
          </p>
        )}
      </Card>

      {/* --- Progres --- */}
      {status && (
        <Card
          title={`Progress · ${status.run_name ?? status.job_id}`}
          subtitle={
            berjalan
              ? "Refreshed automatically every few seconds"
              : "Training has finished"
          }
        >
          <div className="flex flex-wrap items-center gap-3">
            <Lencana status={status.status} />
            <span className="mono text-[12.5px] font-bold text-[var(--ink)]">
              Epoch {status.epoch ?? 0}/{total}
            </span>
            {status.latest?.map50 != null && (
              <span className="text-[12px] text-[var(--muted)]">
                current mAP50{" "}
                <b className="text-[var(--ink)]">{persen(status.latest.map50)}</b>
              </span>
            )}
          </div>

          <div className="h-[9px] w-full overflow-hidden rounded-full bg-[var(--line-soft)]">
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{
                width: `${kemajuan}%`,
                background:
                  status.status === "failed"
                    ? "var(--red)"
                    : "linear-gradient(90deg,#2FBF71,#0F8A55)",
              }}
            />
          </div>

          {status.status === "failed" && status.error && (
            <p
              role="alert"
              className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
            >
              {status.error}
            </p>
          )}

          {status.history.length > 0 ? (
            <div className="grid gap-6 lg:grid-cols-2">
              <TrainingChart
                title="Loss"
                points={status.history}
                series={[
                  { key: "box_loss", label: "box", color: "#2FBF71" },
                  { key: "cls_loss", label: "cls", color: "#E8B93B" },
                  { key: "dfl_loss", label: "dfl", color: "#6C8AE4" },
                ]}
              />
              <TrainingChart
                title="Akurasi"
                points={status.history}
                yMax={1}
                series={[
                  { key: "map50", label: "mAP50", color: "#0F8A55" },
                  { key: "map50_95", label: "mAP50-95", color: "#8AC6A8" },
                ]}
              />
            </div>
          ) : (
            <p className="text-[12px] text-[var(--muted-3)]">
              {berjalan
                ? "Waiting for the first epoch. Preparing the GPU and dataset usually takes one to two minutes."
                : "No per-epoch data for this run."}
            </p>
          )}

          {status.status === "done" && (
            <div className="flex flex-wrap items-center gap-3 rounded-[12px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3">
              <div className="flex-1 text-[12.5px] text-[var(--green-d)]">
                <b>Training complete.</b> mAP50 {persen(status.latest?.map50)} ·
                mAP50-95 {persen(status.latest?.map50_95)}
              </div>
              <button
                onClick={() => aktifkan(status.job_id)}
                disabled={mengaktifkan}
                className="rounded-[10px] bg-[var(--brand)] px-4 py-[9px] text-[12.5px] font-bold text-white disabled:opacity-60"
              >
                {mengaktifkan ? "Downloading weights…" : "Set As Active Model"}
              </button>
            </div>
          )}
        </Card>
      )}

      {/* --- History --- */}
      <Card
        title="Training history"
        subtitle={
          config?.active_model
            ? `Model aktif: ${config.active_model}`
            : "No trained model has been activated yet"
        }
      >
        {runs.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted-3)]">
            No training has been run yet.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-[12.5px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-[var(--muted-3)]">
                  <th className="pb-2 pr-3 font-semibold">Nama</th>
                  <th className="pb-2 pr-3 font-semibold">Date</th>
                  <th className="pb-2 pr-3 font-semibold">Epoch</th>
                  <th className="pb-2 pr-3 font-semibold">mAP50</th>
                  <th className="pb-2 pr-3 font-semibold">Status</th>
                  <th className="pb-2 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-t border-[var(--line-soft)]">
                    <td className="py-[10px] pr-3">
                      <span className="font-semibold text-[var(--ink)]">
                        {run.run_name}
                      </span>
                      <br />
                      <span className="mono text-[10.5px] text-[var(--muted-3)]">
                        {run.base_model}
                        {run.started_by ? ` · ${run.started_by}` : ""}
                      </span>
                    </td>
                    <td className="py-[10px] pr-3 text-[var(--muted)]">
                      {new Date(run.created_at).toLocaleString("en-GB", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </td>
                    <td className="mono py-[10px] pr-3 text-[var(--muted)]">
                      {run.last_epoch ?? 0}/{run.epochs}
                    </td>
                    <td className="mono py-[10px] pr-3 font-bold text-[var(--ink)]">
                      {persen(run.final_map50)}
                    </td>
                    <td className="py-[10px] pr-3">
                      <Lencana status={run.status} />
                      {run.is_active && (
                        <span className="ml-2 text-[10.5px] font-bold text-[var(--brand-2)]">
                          aktif
                        </span>
                      )}
                    </td>
                    <td className="py-[10px]">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => setActiveJob(run.job_id)}
                          className="rounded-[8px] border border-[var(--line)] px-[10px] py-[5px] text-[11.5px] font-semibold text-[var(--brand)]"
                        >
                          View
                        </button>
                        {run.status === "done" && !run.is_active && (
                          <button
                            onClick={() => aktifkan(run.job_id)}
                            disabled={mengaktifkan}
                            className="rounded-[8px] bg-[var(--brand)] px-[10px] py-[5px] text-[11.5px] font-semibold text-white disabled:opacity-60"
                          >
                            Activate
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
          Setting the active model changes the file used for the next
          analysis. Images already analysed do <b>not</b> change —
          re-run analysis if their results need to match the new model.
        </p>
      </Card>
    </>
  );
}
