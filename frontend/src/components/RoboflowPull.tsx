"use client";

import { useEffect, useState } from "react";

import JobMonitor from "@/components/JobMonitor";
import { ApiError, getRoboflowSettings, startRoboflowEvaluation } from "@/lib/api";
import type { Job, RoboflowSettings } from "@/types/detection";

const SPLITS = ["test", "valid", "train"];

/** Pull a dataset version straight from Roboflow and evaluate against it.
 *
 * Replaces two manual uploads. Because the images and their annotations come
 * out of the same archive, their file names always match — the single most
 * common failure of the upload route cannot happen here.
 */
export default function RoboflowPull({ onDone }: { onDone?: () => void }) {
  const [settings, setSettings] = useState<RoboflowSettings | null>(null);
  const [workspace, setWorkspace] = useState("heras-workspace");
  const [project, setProject] = useState("oil-palm-central-kalimantan");
  const [version, setVersion] = useState("3");
  const [split, setSplit] = useState("test");
  const [iou, setIou] = useState("0.5");

  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRoboflowSettings()
      .then(setSettings)
      .catch(() => setSettings(null));
  }, []);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const job = await startRoboflowEvaluation({
        workspace: workspace.trim(),
        project: project.trim(),
        version: Number(version),
        split,
        iou_threshold: Number(iou),
      });
      setJobId(job.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the job.");
    } finally {
      setBusy(false);
    }
  }

  function finished(job: Job) {
    if (job.status === "done") onDone?.();
  }

  const ready = settings?.configured ?? false;

  return (
    <div className="flex flex-col gap-4">
      {settings && !ready && (
        <p className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-3 py-[10px] text-[11.5px] leading-relaxed text-[var(--amber)]">
          <b>Roboflow API key is not set.</b> Add it on the Settings screen to
          pull dataset versions without uploading files.
        </p>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-[170px] flex-1 flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Workspace
          </span>
          <input
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <label className="flex min-w-[210px] flex-1 flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Project
          </span>
          <input
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <label className="flex w-[92px] flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Version
          </span>
          <input
            type="number"
            min={1}
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <label className="flex w-[110px] flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Split
          </span>
          <select
            value={split}
            onChange={(e) => setSplit(e.target.value)}
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          >
            {SPLITS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label className="flex w-[92px] flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            IoU
          </span>
          <input
            type="number"
            step="0.05"
            min="0.05"
            max="0.95"
            value={iou}
            onChange={(e) => setIou(e.target.value)}
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <button
          onClick={start}
          disabled={busy || !ready}
          className="kartu-tekan rounded-[10px] bg-[var(--brand)] px-5 py-[11px] text-[12.5px] font-bold text-white disabled:opacity-50"
        >
          {busy ? "Starting…" : "Pull & Evaluate"}
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

      <JobMonitor jobId={jobId} onFinished={finished} />

      <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
        The chosen split is downloaded, registered, analysed, and scored — no
        files to upload. The dataset version is recorded with the result
        (<code className="mono">roboflow:workspace/project/vN/split</code>)
        rather than a temporary file name, so the evaluation can be repeated by
        someone else. Running this again on the same version reuses the images
        already in the system instead of duplicating them.
      </p>
    </div>
  );
}
