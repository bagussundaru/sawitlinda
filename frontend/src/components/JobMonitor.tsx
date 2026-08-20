"use client";

import { useEffect, useRef, useState } from "react";

import { getJob, listJobs } from "@/lib/api";
import type { Job } from "@/types/detection";

const POLL_MS = 2500;

const STATUS_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  queued: { bg: "var(--line-soft)", fg: "var(--muted)", label: "Queued" },
  running: { bg: "rgba(232,185,59,.16)", fg: "var(--amber)", label: "Running" },
  done: { bg: "rgba(47,191,113,.14)", fg: "var(--brand-2)", label: "Done" },
  failed: { bg: "var(--red-bg)", fg: "var(--red)", label: "Failed" },
};

const KIND_LABEL: Record<string, string> = {
  roboflow_evaluate: "Roboflow evaluation",
  reanalyse: "Re-analysis",
};

function Badge({ status }: { status: string }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.queued;
  return (
    <span
      className="rounded-full px-[10px] py-[3px] text-[11px] font-bold"
      style={{ background: s.bg, color: s.fg }}
    >
      {s.label}
    </span>
  );
}

/** Live view of one background job, plus recent history.
 *
 * Polls only while a job is unfinished — a finished job never changes again,
 * and continuing to ask about it is pure noise on a shared VM.
 */
export default function JobMonitor({
  jobId,
  onFinished,
}: {
  /** Job to follow. Null means "follow whatever is running, if anything". */
  jobId: string | null;
  onFinished?: (job: Job) => void;
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [recent, setRecent] = useState<Job[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sudahLapor = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        // Tanpa jobId, cari sendiri pekerjaan yang sedang berjalan — halaman
        // yang dimuat ulang di tengah pekerjaan tetap menemukannya kembali.
        const target = jobId
          ? await getJob(jobId)
          : (await listJobs()).find(
              (j) => j.status === "running" || j.status === "queued",
            ) ?? null;

        if (cancelled) return;
        setJob(target);

        if (target && (target.status === "done" || target.status === "failed")) {
          if (sudahLapor.current !== target.id) {
            sudahLapor.current = target.id;
            onFinished?.(target);
          }
          listJobs()
            .then((all) => !cancelled && setRecent(all.slice(0, 5)))
            .catch(() => {});
          return; // berhenti bertanya
        }
      } catch {
        // Kegagalan sesaat tidak menghentikan pemantauan.
      }
      if (!cancelled) timer.current = setTimeout(tick, POLL_MS);
    }

    tick();
    listJobs()
      .then((all) => !cancelled && setRecent(all.slice(0, 5)))
      .catch(() => {});

    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [jobId, onFinished]);

  const busy = job?.status === "running" || job?.status === "queued";
  const p = job?.progress;
  const share = p && p.total > 0 ? Math.min(100, (p.current / p.total) * 100) : 0;

  return (
    <div className="flex flex-col gap-3">
      {job && (
        <div className="flex flex-col gap-[9px] rounded-[12px] border border-[var(--line)] p-[13px]">
          <div className="flex flex-wrap items-center gap-2">
            <Badge status={job.status} />
            <span className="text-[12.5px] font-bold text-[var(--ink)]">
              {KIND_LABEL[job.kind] ?? job.kind}
            </span>
            {p && p.total > 0 && (
              <span className="mono text-[11.5px] text-[var(--muted)]">
                {p.current}/{p.total}
              </span>
            )}
            {busy && (
              <span className="titik-sibuk text-[var(--accent)]">
                <span />
                <span />
                <span />
              </span>
            )}
          </div>

          {p?.message && (
            <span className="mono truncate text-[11px] text-[var(--muted-3)]">
              {p.message}
            </span>
          )}

          {p && p.total > 0 && (
            <div className="h-[7px] w-full overflow-hidden rounded-full bg-[var(--line-soft)]">
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${share}%`,
                  background:
                    job.status === "failed"
                      ? "var(--red)"
                      : "linear-gradient(90deg,#2FBF71,#0F8A55)",
                }}
              />
            </div>
          )}

          {job.status === "failed" && job.error && (
            <p
              role="alert"
              className="rounded-[9px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[9px] text-[11.5px] text-[var(--red)]"
            >
              {job.error}
            </p>
          )}

          {job.status === "done" && job.result && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 rounded-[9px] border border-[#bfe6d7] bg-[var(--green-bg)] px-3 py-[9px] text-[11.5px] text-[var(--green-d)]">
              {Object.entries(job.result).map(([k, v]) => (
                <span key={k}>
                  <b>{k.replace(/_/g, " ")}:</b>{" "}
                  {typeof v === "number" ? v.toFixed(3).replace(/\.?0+$/, "") : String(v)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {recent.length > 0 && (
        <div className="flex flex-col gap-[5px]">
          <span className="text-[10.5px] font-bold uppercase tracking-[0.09em] text-[var(--muted-3)]">
            Recent jobs
          </span>
          {recent.map((j) => (
            <div
              key={j.id}
              className="flex items-center justify-between gap-2 text-[11.5px]"
            >
              <span className="truncate text-[var(--muted)]">
                {KIND_LABEL[j.kind] ?? j.kind}
                {j.created_by ? ` · ${j.created_by}` : ""}
              </span>
              <Badge status={j.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
