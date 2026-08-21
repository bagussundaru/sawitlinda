"use client";

import { useEffect, useState } from "react";

import AiKeyCard from "@/components/AiKeyCard";
import RoboflowKeyCard from "@/components/RoboflowKeyCard";
import { Card } from "@/components/Card";
import { ApiError, BASE_URL, getSystemInfo, listConditions } from "@/lib/api";
import { SEVERITY_COLOR, SEVERITY_LABEL } from "@/lib/severity";
import type { ConditionInfo, Severity, SystemInfo } from "@/types/detection";

const SEVERITIES: Severity[] = ["sehat", "ringan", "sedang", "berat"];

export default function SettingsPage() {
  const [conditions, setConditions] = useState<ConditionInfo[] | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listConditions()
      .then(setConditions)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Data failed to load."),
      );
    getSystemInfo()
      .then(setSystem)
      .catch(() => setSystem(null));
  }, []);

  return (
    <div className="space-y-[18px]">
      <div>
        <h1 className="text-[19px] font-bold">Settings</h1>
        <p className="text-[13px] text-[var(--muted)]">
          Plant condition reference and system status.
        </p>
      </div>

      <div className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-[15px] py-3 text-[12.5px] text-[var(--amber)]">
        <b>Inference is still MOCK.</b> Detections are generated synthetically and
        do not reflect image content. Switching to the real model touches one
        fungsi di backend.
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
        >
          {error}
        </p>
      )}

      <AiKeyCard />

      <RoboflowKeyCard />

      <Card title="Plant Condition Reference">
        {conditions ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-[12.5px]">
              <thead>
                <tr className="border-b border-[var(--line)] text-left align-bottom text-[var(--muted)]">
                  <th className="pb-2 font-semibold">Kelas</th>
                  <th className="pb-2 font-semibold">Appearance from above</th>
                  <th className="pb-2 font-semibold">Interpretasi</th>
                  <th className="pb-2 font-semibold">Tindakan</th>
                </tr>
              </thead>
              <tbody>
                {conditions.map((condition) => (
                  <tr
                    key={condition.key}
                    className="border-b border-[var(--line)] align-top last:border-0"
                  >
                    <td className="py-[10px] font-semibold">
                      {condition.label}
                      <div className="font-mono text-[10.5px] font-normal text-[var(--muted)]">
                        {condition.key}
                      </div>
                    </td>
                    <td className="py-[10px] text-[var(--muted)]">
                      {condition.appearance}
                    </td>
                    <td className="py-[10px]">{condition.interpretation}</td>
                    <td className="py-[10px]">{condition.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[12.5px] text-[var(--muted)]">Loading…</p>
        )}
      </Card>

      <div className="grid gap-[18px] lg:grid-cols-2">
        <Card title="Severity Scale">
          <div className="flex flex-wrap gap-4 text-[12.5px]">
            {SEVERITIES.map((severity) => (
              <span key={severity} className="flex items-center gap-[7px]">
                <i
                  className="h-[11px] w-[11px] rounded-[3px]"
                  style={{ background: SEVERITY_COLOR[severity] }}
                />
                {SEVERITY_LABEL[severity]}
              </span>
            ))}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-[var(--muted)]">
            Severity would come from a separate classification head (Swin + MTL). The
            current dataset carries no severity labels, so the value cannot yet be
            defended as a measurement until the client provides them.
          </p>
        </Card>

        <Card title="Detection method" subtitle="The thresholds actually in use">
          {/* Dibaca dari server, bukan ditulis ulang di sini: penjelasan
              metodologis harus ikut berubah dengan sendirinya bila ambangnya
              diubah, tanpa seorang pun harus ingat memperbarui layar ini. */}
          <dl className="space-y-[10px] text-[12.5px]">
            {[
              {
                k: "Detector",
                v: system ? (system.model_loaded ? "YOLOv8" : "mock generator") : "…",
              },
              {
                k: "Model file",
                v: system?.model_name ?? (system ? "none installed" : "…"),
              },
              {
                k: "Confidence threshold",
                v: system ? system.confidence_threshold.toFixed(2) : "…",
              },
              {
                k: "NMS IoU threshold",
                v: system ? system.nms_iou_threshold.toFixed(2) : "…",
              },
              {
                k: "Tile size",
                v: system ? `${system.tile_size} px` : "…",
              },
              {
                k: "Severity source",
                v: system?.severity_source === "rule" ? "fixed rule" : "model",
              },
            ].map((row) => (
              <div key={row.k} className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">{row.k}</dt>
                <dd className="mono truncate font-semibold">{row.v}</dd>
              </div>
            ))}
          </dl>

          <p className="rounded-[10px] border border-[var(--line)] bg-[var(--line-soft)] px-3 py-[10px] text-[11.5px] leading-relaxed text-[var(--muted)]">
            A detection is accepted when YOLOv8 reports a confidence at or above
            the threshold above. Overlapping boxes are merged by non-maximum
            suppression at the IoU threshold. Frames larger than the tile size
            are cut into overlapping tiles before detection, because the model
            was trained on tiles of that size.
            <br />
            <br />
            The confidence of every accepted detection is <b>kept as metadata</b>
            {" "}and appears on the selected tree, the detection detail page, and
            the CSV and PDF exports — it is left off the dashboard lists only
            because, next to a dozen chips, it reads as doubt about whether the
            object is a tree rather than as the acceptance threshold it is.
          </p>
        </Card>

        <Card title="System">
          <dl className="space-y-[10px] text-[12.5px]">
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">API address</dt>
              <dd className="truncate font-mono text-[11.5px]">{BASE_URL}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Inference</dt>
              <dd
                className="font-semibold"
                style={{
                  color: system?.model_loaded ? "var(--brand-2)" : "var(--amber)",
                }}
              >
                {system ? (system.model_loaded ? "Model" : "Mock") : "…"}
              </dd>
            </div>
            {system?.model_error && (
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Engine error</dt>
                <dd
                  className="truncate font-semibold text-[var(--red)]"
                  title={system.model_error}
                >
                  {system.model_error}
                </dd>
              </div>
            )}
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">AI Review</dt>
              <dd
                className="truncate font-semibold"
                style={{
                  color: system?.ai_enabled ? "var(--brand-2)" : "var(--muted-3)",
                }}
                title={system?.ai_model ?? undefined}
              >
                {system ? (system.ai_enabled ? system.ai_model : "Not configured") : "…"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Authentication</dt>
              <dd className="font-semibold text-[var(--brand-2)]">
                Session login
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Supported formats</dt>
              <dd>JPG · PNG · TIFF</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
