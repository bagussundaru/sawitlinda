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
  queued: { bg: "var(--line-soft)", fg: "var(--muted)", label: "Antre" },
  running: { bg: "rgba(232,185,59,.16)", fg: "var(--amber)", label: "Berjalan" },
  done: { bg: "rgba(47,191,113,.14)", fg: "var(--brand-2)", label: "Selesai" },
  failed: { bg: "var(--red-bg)", fg: "var(--red)", label: "Gagal" },
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
  const [aktifJob, setAktifJob] = useState<string | null>(null);
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
        setAktifJob((sekarang) => {
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
      setAktifJob(run.job_id);
      setPesan(`Training "${run.run_name}" dimulai.`);
      muatRuns();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memulai training.");
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
        `Model "${run.run_name}" kini dipakai untuk seluruh analisis berikutnya.`,
      );
      muatRuns();
      getTrainingConfig().then(setConfig).catch(() => {});
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menjadikan model aktif.",
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
          Training Model
        </h1>
        <p className="text-[13px] text-[var(--muted)]">
          Melatih ulang model deteksi pada mesin GPU, lalu menjadikannya model
          yang dipakai aplikasi.
        </p>
      </header>

      {config && !config.configured && (
        <div className="rounded-[12px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-4 py-3 text-[12.5px] leading-relaxed text-[var(--amber)]">
          <b>Mesin training belum dikonfigurasi.</b> Setel{" "}
          <code className="mono">MODAL_TRAINING_URL</code> dan{" "}
          <code className="mono">MODAL_TRAINING_TOKEN</code> di server, lalu
          jalankan ulang backend. Lihat{" "}
          <code className="mono">docs/TRAINING.md</code>.
        </div>
      )}

      {/* --- Formulir --- */}
      <Card
        title="Mulai training baru"
        subtitle="Dataset dalam format YOLOv8 (.zip), berisi data.yaml serta folder train/valid"
      >
        <form onSubmit={mulai} className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[260px] flex-1 flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Berkas dataset
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
                Jumlah epoch
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
                Model dasar
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
                Nama versi (opsional)
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
              {busy ? "Mengunggah…" : "Mulai Training"}
            </button>
          </div>

          <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
            Training berjalan di GPU dan <b>menimbulkan biaya per pemakaian</b>.
            Dataset dikirim ke mesin training sekali, lalu prosesnya berjalan di
            sana — halaman ini boleh ditutup, progresnya tetap tercatat.
            {config ? ` Batas ukuran dataset ${config.max_dataset_mb} MB.` : ""}
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
          title={`Progres · ${status.run_name ?? status.job_id}`}
          subtitle={
            berjalan
              ? "Diperbarui otomatis tiap beberapa detik"
              : "Training telah berakhir"
          }
        >
          <div className="flex flex-wrap items-center gap-3">
            <Lencana status={status.status} />
            <span className="mono text-[12.5px] font-bold text-[var(--ink)]">
              Epoch {status.epoch ?? 0}/{total}
            </span>
            {status.latest?.map50 != null && (
              <span className="text-[12px] text-[var(--muted)]">
                mAP50 saat ini{" "}
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
                ? "Menunggu epoch pertama selesai. Menyiapkan GPU dan dataset biasanya memakan satu hingga dua menit."
                : "Tidak ada data per epoch untuk run ini."}
            </p>
          )}

          {status.status === "done" && (
            <div className="flex flex-wrap items-center gap-3 rounded-[12px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3">
              <div className="flex-1 text-[12.5px] text-[var(--green-d)]">
                <b>Training selesai.</b> mAP50 {persen(status.latest?.map50)} ·
                mAP50-95 {persen(status.latest?.map50_95)}
              </div>
              <button
                onClick={() => aktifkan(status.job_id)}
                disabled={mengaktifkan}
                className="rounded-[10px] bg-[var(--brand)] px-4 py-[9px] text-[12.5px] font-bold text-white disabled:opacity-60"
              >
                {mengaktifkan ? "Mengunduh bobot…" : "Jadikan Model Aktif"}
              </button>
            </div>
          )}
        </Card>
      )}

      {/* --- Riwayat --- */}
      <Card
        title="Riwayat training"
        subtitle={
          config?.active_model
            ? `Model aktif: ${config.active_model}`
            : "Belum ada model hasil training yang diaktifkan"
        }
      >
        {runs.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted-3)]">
            Belum ada training yang pernah dijalankan.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-[12.5px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-[var(--muted-3)]">
                  <th className="pb-2 pr-3 font-semibold">Nama</th>
                  <th className="pb-2 pr-3 font-semibold">Tanggal</th>
                  <th className="pb-2 pr-3 font-semibold">Epoch</th>
                  <th className="pb-2 pr-3 font-semibold">mAP50</th>
                  <th className="pb-2 pr-3 font-semibold">Status</th>
                  <th className="pb-2 font-semibold">Aksi</th>
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
                      {new Date(run.created_at).toLocaleString("id-ID", {
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
                          onClick={() => setAktifJob(run.job_id)}
                          className="rounded-[8px] border border-[var(--line)] px-[10px] py-[5px] text-[11.5px] font-semibold text-[var(--brand)]"
                        >
                          Lihat
                        </button>
                        {run.status === "done" && !run.is_active && (
                          <button
                            onClick={() => aktifkan(run.job_id)}
                            disabled={mengaktifkan}
                            className="rounded-[8px] bg-[var(--brand)] px-[10px] py-[5px] text-[11.5px] font-semibold text-white disabled:opacity-60"
                          >
                            Aktifkan
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
          Menjadikan model aktif mengganti berkas yang dipakai untuk analisis
          berikutnya. Citra yang sudah dianalisis <b>tidak</b> ikut berubah —
          jalankan analisis ulang bila hasilnya perlu disamakan dengan model baru.
        </p>
      </Card>
    </>
  );
}
