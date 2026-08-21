"use client";

/** Catatan eksperimen: registri, hipotesis, hasil, dan pembandingnya.
 *
 * Yang TIDAK ada di sini disengaja: tidak ada tombol menyunting hasil, tidak
 * ada tombol menghapus, dan tidak ada cara memundurkan status. Catatan yang
 * dapat dirapikan setelah angkanya terlihat tidak membuktikan apa pun.
 */

import { useEffect, useMemo, useState } from "react";

import { Card } from "@/components/Card";
import {
  ApiError,
  advanceExperiment,
  attachExperimentResults,
  createExperiment,
  editExperimentDraft,
  listExperiments,
} from "@/lib/api";
import type { Experiment, ExperimentStatus } from "@/types/detection";

const LIFECYCLE: ExperimentStatus[] = [
  "draft",
  "locked",
  "training",
  "ready_for_final_test",
  "final_tested",
];

const LABEL: Record<ExperimentStatus, string> = {
  draft: "DRAFT",
  locked: "LOCKED",
  training: "TRAINING",
  ready_for_final_test: "READY FOR FINAL TEST",
  final_tested: "FINAL TESTED",
};

const WARNA: Record<ExperimentStatus, { background: string; color: string }> = {
  draft: { background: "var(--page)", color: "var(--muted)" },
  locked: { background: "rgba(90,120,255,.13)", color: "#4257c4" },
  training: { background: "var(--amber-bg)", color: "var(--amber)" },
  ready_for_final_test: { background: "rgba(47,191,113,.14)", color: "var(--brand-2)" },
  final_tested: { background: "var(--green-bg)", color: "var(--green-d)" },
};

/** Metrik utama, dalam urutan yang selalu sama supaya dua eksperimen dapat
 * dibaca berdampingan tanpa mencari-cari barisnya. */
const UTAMA: { key: string; label: string }[] = [
  { key: "map50", label: "mAP@50" },
  { key: "map50_95", label: "mAP@50:95" },
  { key: "precision", label: "Precision" },
  { key: "recall", label: "Recall" },
];

const KELAS = ["healthy", "yellow", "small", "dead"];

function waktu(nilai: string): string {
  return new Date(nilai).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function pendek(hash: string | null): string {
  return hash ? `${hash.slice(0, 8)}…` : "—";
}

function angka(nilai: unknown): string {
  return typeof nilai === "number" ? nilai.toFixed(4) : "—";
}

function Lencana({ status }: { status: ExperimentStatus }) {
  return (
    <span
      className="whitespace-nowrap rounded-md px-[7px] py-[2px] text-[10px] font-bold tracking-[0.04em]"
      style={WARNA[status]}
    >
      {LABEL[status]}
    </span>
  );
}

function Galat({ pesan }: { pesan: string | null }) {
  if (!pesan) return null;
  return (
    <p
      role="alert"
      className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] leading-relaxed text-[var(--red)]"
    >
      {pesan}
    </p>
  );
}

/** Ambil metrik per-kelas apa pun bentuk penyimpanannya:
 * `per_class: {healthy: {ap: …}}` atau `ap_healthy: …` sama-sama diterima. */
function perKelas(metrics: Record<string, unknown>, kelas: string, bidang: string) {
  const tabel = metrics.per_class as Record<string, Record<string, unknown>> | undefined;
  if (tabel && tabel[kelas] && tabel[kelas][bidang] !== undefined) {
    return tabel[kelas][bidang];
  }
  return metrics[`${bidang}_${kelas}`];
}

export default function ExperimentRegistry() {
  const [daftar, setDaftar] = useState<Experiment[]>([]);
  const [dipilih, setDipilih] = useState<string | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const [bukaForm, setBukaForm] = useState(false);

  async function muat() {
    try {
      const list = await listExperiments();
      setDaftar(list);
      setDipilih((lama) =>
        lama && list.some((e) => e.experiment_id === lama)
          ? lama
          : (list[0]?.experiment_id ?? null),
      );
    } catch {
      setDaftar([]);
    }
  }

  useEffect(() => {
    void muat();
  }, []);

  const aktif = daftar.find((e) => e.experiment_id === dipilih) ?? null;

  async function jalankan(aksi: () => Promise<unknown>) {
    setSibuk(true);
    setGalat(null);
    try {
      await aksi();
      await muat();
    } catch (err) {
      setGalat(err instanceof ApiError ? err.message : "Request failed.");
    } finally {
      setSibuk(false);
    }
  }

  return (
    <>
      <Card
        title="Experiment Registry"
        subtitle="Every recorded experiment. Records are immutable once results are attached."
      >
        <Galat pesan={galat} />

        {daftar.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted-2)]">
            No experiments recorded yet. Register one before training starts — a
            hypothesis written after the numbers are known proves nothing.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-[12px]">
              <thead>
                <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
                  <th className="pb-2 font-semibold">Experiment ID</th>
                  <th className="pb-2 font-semibold">Model</th>
                  <th className="pb-2 font-semibold">Dataset</th>
                  <th className="pb-2 font-semibold">Test hash</th>
                  <th className="pb-2 font-semibold">Status</th>
                  <th className="pb-2 font-semibold">Recorded</th>
                </tr>
              </thead>
              <tbody>
                {daftar.map((e) => (
                  <tr
                    key={e.id}
                    onClick={() => setDipilih(e.experiment_id)}
                    className="cursor-pointer border-b border-[var(--line)] last:border-0 hover:bg-[var(--page)]"
                    style={
                      e.experiment_id === dipilih
                        ? { background: "var(--page)" }
                        : undefined
                    }
                  >
                    <td className="py-[9px] font-semibold">
                      {e.experiment_id}
                      <span className="ml-2 text-[10.5px] font-normal text-[var(--muted-3)]">
                        {e.kind}
                      </span>
                    </td>
                    <td className="py-[9px]">{e.model_name ?? pendek(e.model_id)}</td>
                    <td className="py-[9px]">{e.dataset_name}</td>
                    <td className="mono py-[9px] text-[11px]">
                      {pendek(e.dataset_test_hash)}
                    </td>
                    <td className="py-[9px]">
                      <Lencana status={e.status} />
                    </td>
                    <td className="py-[9px] text-[var(--muted-2)]">
                      {waktu(e.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div>
          <button
            onClick={() => setBukaForm((v) => !v)}
            className="rounded-[10px] border border-[var(--line)] bg-white px-4 py-[9px] text-[13px] font-semibold"
          >
            {bukaForm ? "Cancel" : "Register new experiment"}
          </button>
        </div>

        {bukaForm && (
          <FormBaru
            sibuk={sibuk}
            onSubmit={(body) =>
              jalankan(async () => {
                const baru = await createExperiment(body);
                setDipilih(baru.experiment_id);
                setBukaForm(false);
              })
            }
          />
        )}
      </Card>

      {aktif && (
        <>
          <Hipotesis
            experiment={aktif}
            sibuk={sibuk}
            onSave={(hypothesis) =>
              jalankan(() => editExperimentDraft(aktif.experiment_id, { hypothesis }))
            }
            onAdvance={(status) =>
              jalankan(() => advanceExperiment(aktif.experiment_id, status))
            }
          />
          <Hasil
            experiment={aktif}
            sibuk={sibuk}
            onAttach={(metrics) =>
              jalankan(() => attachExperimentResults(aktif.experiment_id, metrics))
            }
          />
        </>
      )}

      <Pembanding daftar={daftar} />
    </>
  );
}

// --- Pendaftaran ----------------------------------------------------------

function FormBaru({
  sibuk,
  onSubmit,
}: {
  sibuk: boolean;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [nilai, setNilai] = useState({
    experiment_id: "",
    kind: "test",
    model_id: "",
    model_name: "",
    dataset_name: "",
    dataset_test_hash: "",
    hypothesis: "",
  });

  const ubah = (k: string) => (e: { target: { value: string } }) =>
    setNilai((v) => ({ ...v, [k]: e.target.value }));

  const bidang = "rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[13px]";

  return (
    <div className="flex flex-col gap-3 rounded-[12px] border border-[var(--line)] bg-[var(--page)] p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Experiment ID
          </span>
          <input
            className={bidang}
            value={nilai.experiment_id}
            onChange={ubah("experiment_id")}
            placeholder="B1-dji-only"
          />
        </label>
        <label className="flex flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">Kind</span>
          <select className={bidang} value={nilai.kind} onChange={ubah("kind")}>
            <option value="test">test</option>
            <option value="validation">validation</option>
          </select>
        </label>
        <label className="flex flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Model checkpoint SHA-256
          </span>
          <input
            className={`${bidang} mono`}
            value={nilai.model_id}
            onChange={ubah("model_id")}
          />
        </label>
        <label className="flex flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Model file name
          </span>
          <input
            className={bidang}
            value={nilai.model_name}
            onChange={ubah("model_name")}
            placeholder="b1-best.pt"
          />
        </label>
        <label className="flex flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Training dataset
          </span>
          <input
            className={bidang}
            value={nilai.dataset_name}
            onChange={ubah("dataset_name")}
          />
        </label>
        <label className="flex flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Test set SHA-256
          </span>
          <input
            className={`${bidang} mono`}
            value={nilai.dataset_test_hash}
            onChange={ubah("dataset_test_hash")}
          />
        </label>
      </div>

      <label className="flex flex-col gap-[6px]">
        <span className="text-[12px] font-semibold text-[var(--muted)]">
          Hypothesis — written now, before the numbers exist
        </span>
        <textarea
          className={`${bidang} min-h-[86px]`}
          value={nilai.hypothesis}
          onChange={ubah("hypothesis")}
          placeholder="B2 will score worse on test than B1 despite having more training data, because the extra images come from mosaics that do not resemble the standalone frames."
        />
      </label>

      <div>
        <button
          onClick={() =>
            onSubmit({
              ...nilai,
              model_name: nilai.model_name || null,
              hypothesis: nilai.hypothesis || null,
            })
          }
          disabled={sibuk}
          className="rounded-[11px] bg-[var(--brand)] px-5 py-[11px] text-[13px] font-bold text-white disabled:opacity-60"
        >
          {sibuk ? "Recording…" : "Record experiment"}
        </button>
      </div>
    </div>
  );
}

// --- Hipotesis ------------------------------------------------------------

function Hipotesis({
  experiment,
  sibuk,
  onSave,
  onAdvance,
}: {
  experiment: Experiment;
  sibuk: boolean;
  onSave: (hypothesis: string) => void;
  onAdvance: (status: ExperimentStatus) => void;
}) {
  const draft = experiment.status === "draft";
  const [teks, setTeks] = useState(experiment.hypothesis ?? "");

  useEffect(() => {
    setTeks(experiment.hypothesis ?? "");
  }, [experiment.experiment_id, experiment.hypothesis]);

  const indeks = LIFECYCLE.indexOf(experiment.status);
  // `final_tested` tidak pernah ditawarkan: status itu hanya diperoleh dengan
  // benar-benar melampirkan hasil.
  const berikutnya =
    indeks >= 0 && indeks < LIFECYCLE.indexOf("final_tested") - 1
      ? LIFECYCLE[indeks + 1]
      : null;

  return (
    <Card
      title={`Hypothesis — ${experiment.experiment_id}`}
      subtitle={
        draft
          ? "Editable while this experiment is still a draft"
          : "Frozen when the experiment left draft"
      }
    >
      {draft ? (
        <>
          <textarea
            value={teks}
            onChange={(e) => setTeks(e.target.value)}
            className="min-h-[100px] rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[13px] leading-relaxed"
          />
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => onSave(teks)}
              disabled={sibuk}
              className="rounded-[11px] border border-[var(--line)] bg-white px-4 py-[10px] text-[13px] font-semibold disabled:opacity-60"
            >
              Save hypothesis
            </button>
            <button
              onClick={() => onAdvance("locked")}
              disabled={sibuk}
              className="rounded-[11px] bg-[var(--brand)] px-5 py-[10px] text-[13px] font-bold text-white disabled:opacity-60"
            >
              Lock experiment
            </button>
          </div>
          <p className="text-[11.5px] leading-relaxed text-[var(--muted-2)]">
            Locking is one-way. After that the hypothesis and the dataset
            identity cannot be edited — that is what makes the freeze mean
            something.
          </p>
        </>
      ) : (
        <>
          <blockquote className="rounded-[10px] border-l-[3px] border-[var(--brand)] bg-[var(--page)] px-4 py-3 text-[13px] leading-relaxed">
            {experiment.hypothesis || (
              <span className="text-[var(--muted-3)]">
                No hypothesis was recorded before this experiment was locked.
              </span>
            )}
          </blockquote>
          <div className="flex flex-wrap items-center gap-3">
            <Lencana status={experiment.status} />
            {berikutnya && (
              <button
                onClick={() => onAdvance(berikutnya)}
                disabled={sibuk}
                className="rounded-[11px] bg-[var(--brand)] px-4 py-[9px] text-[13px] font-bold text-white disabled:opacity-60"
              >
                Advance to {LABEL[berikutnya]}
              </button>
            )}
          </div>
        </>
      )}
    </Card>
  );
}

// --- Hasil ----------------------------------------------------------------

function Hasil({
  experiment,
  sibuk,
  onAttach,
}: {
  experiment: Experiment;
  sibuk: boolean;
  onAttach: (metrics: Record<string, unknown>) => void;
}) {
  const [json, setJson] = useState("");
  const [galat, setGalat] = useState<string | null>(null);
  const metrics = experiment.metrics;

  if (!metrics) {
    const siap = experiment.status === "ready_for_final_test";
    return (
      <Card title="Results" subtitle="Attached once, after the model is final">
        {siap ? (
          <>
            <textarea
              value={json}
              onChange={(e) => setJson(e.target.value)}
              placeholder='{"map50": 0.61, "map50_95": 0.34, "precision": 0.70, "recall": 0.58, "per_class": {"healthy": {"ap": 0.72, "instances": 412}}}'
              className="mono min-h-[120px] rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[12px]"
            />
            <Galat pesan={galat} />
            <div>
              <button
                onClick={() => {
                  try {
                    setGalat(null);
                    onAttach(JSON.parse(json) as Record<string, unknown>);
                  } catch {
                    setGalat("That is not valid JSON.");
                  }
                }}
                disabled={sibuk}
                className="rounded-[11px] bg-[var(--brand)] px-5 py-[11px] text-[13px] font-bold text-white disabled:opacity-60"
              >
                Attach results
              </button>
            </div>
            <p className="text-[11.5px] leading-relaxed text-[var(--muted-2)]">
              Results can be attached only once. There is no way to edit or
              replace them afterwards — record a new experiment instead.
            </p>
          </>
        ) : (
          <p className="text-[12.5px] leading-relaxed text-[var(--muted-2)]">
            This experiment is <b>{LABEL[experiment.status]}</b>. A final test can
            only be recorded once it reaches{" "}
            <b>{LABEL.ready_for_final_test}</b> — the model must be final before
            the test set is touched.
          </p>
        )}
      </Card>
    );
  }

  return (
    <Card
      title="Results"
      subtitle={`Recorded ${experiment.results_at ? waktu(experiment.results_at) : "—"} · immutable`}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {UTAMA.map((m) => (
          <div
            key={m.key}
            className="rounded-[12px] border border-[var(--line)] bg-[var(--page)] px-4 py-3"
          >
            <div className="text-[11px] font-semibold text-[var(--muted)]">
              {m.label}
            </div>
            <div className="mono mt-1 text-[19px] font-extrabold tabular-nums">
              {angka(metrics[m.key])}
            </div>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-[12px]">
          <thead>
            <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
              <th className="pb-2 font-semibold">Class</th>
              <th className="pb-2 text-right font-semibold">AP@50</th>
              <th className="pb-2 text-right font-semibold">GT instances</th>
            </tr>
          </thead>
          <tbody>
            {KELAS.map((k) => (
              <tr key={k} className="border-b border-[var(--line)] last:border-0">
                <td className="py-[9px] font-semibold">{k}</td>
                <td className="mono py-[9px] text-right tabular-nums">
                  {angka(perKelas(metrics, k, "ap"))}
                </td>
                <td className="mono py-[9px] text-right tabular-nums">
                  {String(perKelas(metrics, k, "instances") ?? "—")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="grid gap-x-6 gap-y-2 text-[11.5px] sm:grid-cols-2">
        {[
          ["Test set SHA-256", experiment.dataset_test_hash],
          ["Training dataset", experiment.dataset_name],
          ["Model checkpoint", experiment.model_name ?? experiment.model_id],
          ["Git commit", experiment.git_commit ?? "—"],
          ["Recorded by", experiment.created_by ?? "—"],
          ["Registered", waktu(experiment.created_at)],
        ].map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="shrink-0 font-semibold text-[var(--muted)]">{k}</dt>
            <dd className="mono break-all text-[var(--muted-2)]">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

// --- Pembanding -----------------------------------------------------------

function Pembanding({ daftar }: { daftar: Experiment[] }) {
  const selesai = useMemo(
    () => daftar.filter((e) => e.metrics && e.kind === "test").slice(0, 4).reverse(),
    [daftar],
  );

  if (selesai.length < 2) return null;

  const dasar = selesai[0];
  const hashSama = selesai.every(
    (e) => e.dataset_test_hash === dasar.dataset_test_hash,
  );

  const baris: { label: string; ambil: (e: Experiment) => unknown }[] = [
    ...UTAMA.map((m) => ({
      label: m.label,
      ambil: (e: Experiment) => e.metrics?.[m.key],
    })),
    ...KELAS.map((k) => ({
      label: `AP@50 · ${k}`,
      ambil: (e: Experiment) => perKelas(e.metrics ?? {}, k, "ap"),
    })),
  ];

  return (
    <Card
      title="Compare Experiments"
      subtitle={`Δ is measured against ${dasar.experiment_id}`}
    >
      {hashSama ? (
        <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3 text-[12.5px] text-[var(--green-d)]">
          <b>Test dataset identik:</b>{" "}
          <span className="mono">{dasar.dataset_test_hash.slice(0, 16)}…</span> —
          these numbers were measured on the same test set, so the differences
          are comparable.
        </div>
      ) : (
        <div className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-4 py-3 text-[12.5px] leading-relaxed text-[var(--amber)]">
          <b>Test sets differ.</b> These experiments were not measured on the
          same data, so the Δ column compares numbers that are not directly
          comparable.
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[12px]">
          <thead>
            <tr className="border-b border-[var(--line)] text-left text-[var(--muted)]">
              <th className="pb-2 font-semibold">Metric</th>
              {selesai.map((e) => (
                <th key={e.id} className="pb-2 text-right font-semibold">
                  {e.experiment_id}
                </th>
              ))}
              <th className="pb-2 text-right font-semibold">Δ</th>
            </tr>
          </thead>
          <tbody>
            {baris.map((b) => {
              const nilai = selesai.map((e) => b.ambil(e));
              const awal = nilai[0];
              const akhir = nilai[nilai.length - 1];
              const delta =
                typeof awal === "number" && typeof akhir === "number"
                  ? akhir - awal
                  : null;
              return (
                <tr key={b.label} className="border-b border-[var(--line)] last:border-0">
                  <td className="py-[9px] font-semibold">{b.label}</td>
                  {nilai.map((v, i) => (
                    <td key={i} className="mono py-[9px] text-right tabular-nums">
                      {angka(v)}
                    </td>
                  ))}
                  <td
                    className="mono py-[9px] text-right font-semibold tabular-nums"
                    style={{
                      color:
                        delta === null || Math.abs(delta) < 1e-9
                          ? "var(--muted-3)"
                          : delta > 0
                            ? "var(--brand-2)"
                            : "var(--red)",
                    }}
                  >
                    {delta === null
                      ? "—"
                      : `${delta > 0 ? "+" : ""}${delta.toFixed(4)}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
