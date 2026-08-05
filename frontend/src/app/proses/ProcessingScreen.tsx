"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, analyzeImage } from "@/lib/api";

const STAGES = [
  { name: "Preprocessing", detail: "validasi · EXIF · GPS" },
  { name: "YOLOv8", detail: "deteksi area" },
  { name: "Swin + MTL", detail: "klasifikasi" },
  { name: "Hasil", detail: "label · severity" },
];

const STATUSES = [
  "Memuat model…",
  "Memvalidasi berkas & membaca EXIF…",
  "YOLOv8 mendeteksi area…",
  "Swin Transformer + MTL mengklasifikasi…",
  "Menyusun hasil…",
];

const STEP_MS = 620;

export default function ProcessingScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").filter(Boolean);

  const [step, setStep] = useState(0);
  const [done, setDone] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  // The stage animation is cosmetic; it walks forward on a timer but parks on the
  // last stage until the real request comes back, so it can never claim to be
  // finished before the analysis actually is.
  useEffect(() => {
    const timer = setInterval(
      () => setStep((current) => Math.min(current + 1, STAGES.length - 1)),
      STEP_MS,
    );
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    if (ids.length === 0) {
      router.replace("/");
      return;
    }

    (async () => {
      try {
        for (const [index, id] of ids.entries()) {
          await analyzeImage(id);
          setDone(index + 1);
        }
        router.replace(ids.length === 1 ? `/hasil/${ids[0]}` : "/riwayat");
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Analisis gagal dijalankan.",
        );
      }
    })();
  }, [ids, router]);

  const progress = error
    ? 100
    : Math.round(((step + 1) / (STAGES.length + 1)) * 100);

  return (
    <div className="mx-auto mt-[30px] max-w-[520px] text-center">
      <h2 className="text-xl font-bold">
        {error ? "Analisis gagal" : "Menganalisis citra…"}
      </h2>

      <div className="my-[34px] flex items-center justify-center">
        {STAGES.map((stage, index) => (
          <div key={stage.name} className="flex flex-1 items-center">
            <div
              className={`flex-1 rounded-xl border px-[6px] py-[14px] text-[12.5px] font-semibold transition ${
                index < step
                  ? "border-[var(--green-l)] bg-[var(--green-bg)] text-[var(--green-d)]"
                  : index === step && !error
                    ? "scale-105 border-[var(--green)] bg-[var(--green)] text-white"
                    : "border-[var(--line)] bg-[var(--card)] text-[var(--muted)]"
              }`}
            >
              {stage.name}
              <small className="mt-[2px] block text-[10.5px] font-normal opacity-85">
                {stage.detail}
              </small>
            </div>
            {index < STAGES.length - 1 && (
              <span className="px-1 text-lg text-[var(--line)]">→</span>
            )}
          </div>
        ))}
      </div>

      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--line)]">
        <div
          className="h-full rounded-full bg-[var(--green-l)] transition-[width] duration-300"
          style={{
            width: `${progress}%`,
            background: error ? "var(--red)" : undefined,
          }}
        />
      </div>

      {error ? (
        <>
          <p role="alert" className="mt-[14px] text-[13px] text-[var(--red)]">
            {error}
          </p>
          <button
            onClick={() => router.push("/")}
            className="mt-4 rounded-[9px] bg-[var(--green)] px-5 py-[10px] text-[13.5px] font-semibold text-white hover:bg-[var(--green-d)]"
          >
            Kembali ke unggah
          </button>
        </>
      ) : (
        <>
          <p className="mt-[14px] text-[13px] text-[var(--muted)]">
            {STATUSES[Math.min(step, STATUSES.length - 1)]}
            {ids.length > 1 && ` · citra ${done + 1} dari ${ids.length}`}
          </p>
          <p className="mt-2 text-[11px] leading-relaxed text-[var(--muted-3)]">
            Tahap YOLOv8 dan Swin + MTL menggambarkan pipeline yang dituju.
            Selama inference masih mock, keduanya belum benar-benar dijalankan.
          </p>
        </>
      )}
    </div>
  );
}
