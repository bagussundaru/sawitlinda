"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Card, StatCard } from "@/components/Card";
import { ConditionBars, HealthDonut } from "@/components/Charts";
import DronePanel from "@/components/DronePanel";
import ImageStrip from "@/components/ImageStrip";
import InferenceQueue from "@/components/InferenceQueue";
import { ApiError, getDashboard, getResult, listResults } from "@/lib/api";
import type {
  Dashboard,
  DetectionResult,
  ResultListItem,
} from "@/types/detection";

/** Jeda sebelum pencarian dikirim. Tanpa ini setiap ketukan tombol menjadi satu
 *  permintaan, dan jawaban lama bisa tiba setelah jawaban baru. */
const JEDA_CARI_MS = 300;

function KerangkaAngka() {
  return (
    <div className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="kerangka h-[104px]" />
      ))}
    </div>
  );
}

export default function HomePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [history, setHistory] = useState<ResultListItem[]>([]);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [cari, setCari] = useState("");
  const [kunci, setKunci] = useState("");
  const [memuat, setMemuat] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pencarian ditunda; `kunci` yang benar-benar dikirim ke server.
  useEffect(() => {
    const t = setTimeout(() => setKunci(cari), JEDA_CARI_MS);
    return () => clearTimeout(t);
  }, [cari]);

  useEffect(() => {
    let dibatalkan = false;
    setMemuat(true);
    (async () => {
      try {
        const [dashboard, daftar] = await Promise.all([
          getDashboard(kunci),
          listResults(),
        ]);
        if (dibatalkan) return;

        const cocok = kunci.trim()
          ? daftar.filter((item) =>
              (item.label ?? item.filename)
                .toLowerCase()
                .includes(kunci.trim().toLowerCase()),
            )
          : daftar;

        setData(dashboard);
        setHistory(cocok);
        setError(null);

        // Citra pertama yang sudah dianalisis dibuka otomatis, supaya panel
        // kanan tidak pernah kosong ketika ada sesuatu untuk ditampilkan.
        const pertama = cocok.find((item) => item.status === "analyzed");
        setResult(pertama ? await getResult(pertama.image_id) : null);
        setHighlighted(null);
      } catch (err) {
        if (!dibatalkan) {
          setError(err instanceof ApiError ? err.message : "Data gagal dimuat.");
        }
      } finally {
        if (!dibatalkan) setMemuat(false);
      }
    })();
    return () => {
      dibatalkan = true;
    };
  }, [kunci]);

  async function pilihCitra(item: ResultListItem) {
    if (item.status !== "analyzed" || item.image_id === result?.image_id) return;
    try {
      setResult(await getResult(item.image_id));
      setHighlighted(null);
    } catch {
      /* panel tetap menampilkan citra sebelumnya */
    }
  }

  const dianalisis = useMemo(
    () => history.filter((item) => item.status === "analyzed"),
    [history],
  );

  if (error) {
    return (
      <p
        role="alert"
        className="muncul rounded-[12px] border border-[#f0c9c9] bg-[var(--red-bg)] px-4 py-3 text-[12.5px] text-[var(--red)]"
      >
        {error}
      </p>
    );
  }

  const summary = data?.summary;
  const share = (n: number) =>
    summary && summary.total > 0 ? n / summary.total : 0;

  return (
    <>
      <header className="muncul flex flex-wrap items-center justify-between gap-5">
        <div>
          <div className="text-[11px] font-bold tracking-[0.15em] text-[#5c7a6b]">
            DASHBOARD OPERASIONAL
          </div>
          <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
            Analisis Kondisi Tanaman
          </h1>
        </div>
        <div className="flex items-center gap-[10px]">
          <span className="mono hidden rounded-[11px] border border-[var(--line)] bg-[var(--card)] px-[14px] py-[10px] text-[11px] text-[var(--muted-3)] sm:block">
            {data ? `${data.images_analyzed}/${data.images_total} citra dianalisis` : "memuat…"}
          </span>
          <Link
            href="/unggah"
            className="kartu-tekan rounded-[11px] bg-[var(--brand)] px-[18px] py-[11px] text-[12.5px] font-bold text-white"
          >
            Unggah &amp; Analisis
          </Link>
        </div>
      </header>

      {data?.images_analyzed === 0 && !kunci && (
        <div className="muncul rounded-[12px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3 text-[12.5px] text-[var(--green-d)]">
          Belum ada citra yang dianalisis.{" "}
          <Link href="/unggah" className="font-bold underline">
            Unggah citra pertama
          </Link>{" "}
          untuk mengisi dashboard ini.
        </div>
      )}

      {/* --- Pencarian label --- */}
      <div className="muncul relative max-w-[420px]" style={{ ["--i" as string]: 1 }}>
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="pointer-events-none absolute left-[13px] top-1/2 -translate-y-1/2 text-[var(--muted-3)]"
          aria-hidden
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" strokeLinecap="round" />
        </svg>
        <input
          value={cari}
          onChange={(e) => setCari(e.target.value)}
          placeholder="Cari label citra…"
          aria-label="Cari label citra"
          className="w-full rounded-[11px] border border-[var(--line)] bg-[var(--card)] py-[10px] pl-[36px] pr-[34px] text-[12.5px] outline-none transition focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_rgba(47,191,113,.14)]"
        />
        {cari && (
          <button
            onClick={() => setCari("")}
            aria-label="Kosongkan pencarian"
            className="absolute right-[10px] top-1/2 -translate-y-1/2 rounded-full px-[6px] text-[15px] leading-none text-[var(--muted-3)] hover:text-[var(--ink)]"
          >
            ×
          </button>
        )}
      </div>

      {/* --- Angka ringkas --- */}
      {memuat || !summary ? (
        <KerangkaAngka />
      ) : (
        <section className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
          {[
            {
              label: "Total Pohon Terdeteksi",
              value: summary.total,
              share: 1,
              note: `${data?.images_analyzed ?? 0} citra`,
              color: undefined,
            },
            {
              label: "Pohon Sehat",
              value: summary.healthy,
              share: share(summary.healthy),
              color: "var(--healthy)",
            },
            {
              label: "Pohon Bermasalah",
              value: summary.infected,
              share: share(summary.infected),
              color: "var(--mild)",
            },
            {
              label: "Kasus Berat",
              value: summary.severe,
              share: share(summary.severe),
              color: "var(--severe)",
            },
          ].map((kartu, i) => (
            <div key={kartu.label} className="muncul" style={{ ["--i" as string]: i }}>
              <StatCard {...kartu} />
            </div>
          ))}
        </section>
      )}

      {/* --- Pemilih citra + panel hasil --- */}
      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <div className="muncul" style={{ ["--i" as string]: 2 }}>
          <Card
            title="Citra Terpindai"
            subtitle="Klik satu citra untuk membuka hasil deteksinya"
            action={
              <Link
                href="/riwayat"
                className="text-[11.5px] font-bold text-[var(--brand-2)]"
              >
                Semua citra →
              </Link>
            }
          >
            <ImageStrip
              items={dianalisis}
              selectedId={result?.image_id ?? null}
              onSelect={pilihCitra}
              loading={memuat}
            />
          </Card>
        </div>

        <div className="muncul" style={{ ["--i" as string]: 3 }}>
          <DronePanel
            result={result}
            highlighted={highlighted}
            onHighlight={setHighlighted}
            loading={memuat}
          />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <div className="muncul" style={{ ["--i" as string]: 4 }}>
          <Card title="Distribusi Kondisi Tanaman">
            {memuat || !data ? (
              <div className="kerangka h-[190px]" />
            ) : (
              <ConditionBars
                items={data.by_condition}
                focused={focus}
                onFocus={setFocus}
              />
            )}
          </Card>
        </div>

        <div className="muncul" style={{ ["--i" as string]: 5 }}>
          <Card title="Rasio Sehat vs Bermasalah">
            {memuat || !summary ? (
              <div className="kerangka h-[190px]" />
            ) : (
              <HealthDonut healthy={summary.healthy} affected={summary.infected} />
            )}
          </Card>
        </div>
      </section>

      <section className="muncul grid gap-4" style={{ ["--i" as string]: 6 }}>
        <Card title="Antrian Inference" subtitle="Status citra yang masuk ke sistem">
          <InferenceQueue items={history} />
        </Card>
      </section>
    </>
  );
}
