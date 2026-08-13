"use client";

import { useEffect, useState } from "react";

import AiKeyCard from "@/components/AiKeyCard";
import { Card } from "@/components/Card";
import { ApiError, BASE_URL, getSystemInfo, listConditions } from "@/lib/api";
import { SEVERITY_COLOR } from "@/lib/severity";
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
        <Card title="Skala Keparahan">
          <div className="flex flex-wrap gap-4 text-[12.5px]">
            {SEVERITIES.map((severity) => (
              <span key={severity} className="flex items-center gap-[7px]">
                <i
                  className="h-[11px] w-[11px] rounded-[3px]"
                  style={{ background: SEVERITY_COLOR[severity] }}
                />
                {severity}
              </span>
            ))}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-[var(--muted)]">
            Severity would come from a separate classification head (Swin + MTL). The
            current dataset carries no severity labels, so the value cannot yet be
            dipertanggungjawabkan sampai klien menyediakannya.
          </p>
        </Card>

        <Card title="Sistem">
          <dl className="space-y-[10px] text-[12.5px]">
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Alamat API</dt>
              <dd className="truncate font-mono text-[11.5px]">{BASE_URL}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Status inference</dt>
              <dd className="font-semibold text-[var(--amber)]">Mock</dd>
            </div>
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
              <dt className="text-[var(--muted)]">Autentikasi</dt>
              <dd className="font-semibold text-[var(--red)]">Not available</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-[var(--muted)]">Format didukung</dt>
              <dd>JPG · PNG · TIFF</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
