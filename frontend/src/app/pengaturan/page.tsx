"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, BASE_URL, listConditions } from "@/lib/api";
import { SEVERITY_COLOR } from "@/lib/severity";
import type { ConditionInfo, Severity } from "@/types/detection";

const SEVERITIES: Severity[] = ["sehat", "ringan", "sedang", "berat"];

export default function PengaturanPage() {
  const [conditions, setConditions] = useState<ConditionInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listConditions()
      .then(setConditions)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Data gagal dimuat."),
      );
  }, []);

  return (
    <div className="space-y-[18px]">
      <div>
        <h1 className="text-[19px] font-bold">Pengaturan</h1>
        <p className="text-[13px] text-[var(--muted)]">
          Acuan kondisi tanaman dan status sistem.
        </p>
      </div>

      <div className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-[15px] py-3 text-[12.5px] text-[var(--amber)]">
        <b>Inference masih MOCK.</b> Hasil deteksi dibangkitkan secara sintetis dan
        belum mencerminkan isi citra. Mengganti ke model asli cukup menyentuh satu
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

      <Card title="Acuan Kondisi Tanaman">
        {conditions ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-[12.5px]">
              <thead>
                <tr className="border-b border-[var(--line)] text-left align-bottom text-[var(--muted)]">
                  <th className="pb-2 font-semibold">Kelas</th>
                  <th className="pb-2 font-semibold">Ciri dari citra atas</th>
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
          <p className="text-[12.5px] text-[var(--muted)]">Memuat…</p>
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
            Keparahan berasal dari kepala klasifikasi terpisah (Swin + MTL). Dataset
            saat ini belum memuat label keparahan, sehingga nilainya belum dapat
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
              <dt className="text-[var(--muted)]">Autentikasi</dt>
              <dd className="font-semibold text-[var(--red)]">Belum tersedia</dd>
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
