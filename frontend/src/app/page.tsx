"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card, StatCard } from "@/components/Card";
import { ConditionBars, HealthDonut } from "@/components/Charts";
import DronePanel from "@/components/DronePanel";
import InferenceQueue from "@/components/InferenceQueue";
import ResultTable, { type UrutanTabel } from "@/components/ResultTable";
import { ApiError, getDashboard, getResult, listResults } from "@/lib/api";
import type {
  Dashboard,
  DetectionResult,
  ResultListItem,
  ResultSort,
} from "@/types/detection";

/** Baris per halaman. Cukup untuk satu layar tanpa menggulir jauh, dan jauh di
 *  bawah batas 200 yang ditegakkan server. */
const PER_HALAMAN = 25;

/** Jeda sebelum pencarian dikirim. Tanpa ini setiap ketukan tombol menjadi satu
 *  permintaan, dan jawaban lama bisa tiba setelah jawaban baru. */
const JEDA_CARI_MS = 300;

/** Warna per kelas kondisi. Kuncinya label dari server, bukan kunci kelas —
 *  itulah yang dikirim `by_condition`. */
const CONDITION_COLOR: Record<string, string | undefined> = {
  Healthy: "var(--healthy)",
  Yellowing: "var(--mild)",
  Stunted: "var(--mild)",
  "Dead / stressed": "var(--severe)",
};

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
  const [total, setTotal] = useState(0);
  const [halaman, setHalaman] = useState(0);
  const [urutan, setUrutan] = useState<UrutanTabel>({
    sort: "created_at",
    order: "desc",
  });
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [cari, setCari] = useState("");
  const [kunci, setKunci] = useState("");
  const [memuat, setMemuat] = useState(true);
  const [memuatCitra, setMemuatCitra] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pencarian ditunda; `kunci` yang benar-benar dikirim ke server.
  useEffect(() => {
    const t = setTimeout(() => setKunci(cari), JEDA_CARI_MS);
    return () => clearTimeout(t);
  }, [cari]);

  // Pencarian atau pengurutan yang berubah mengembalikan daftar ke halaman
  // pertama; bertahan di halaman 7 setelah menyaring hanya menampilkan layar
  // kosong.
  useEffect(() => {
    setHalaman(0);
  }, [kunci, urutan]);

  useEffect(() => {
    let dibatalkan = false;
    setMemuat(true);
    (async () => {
      try {
        const [dashboard, halamanHasil] = await Promise.all([
          getDashboard(kunci),
          listResults({
            q: kunci,
            sort: urutan.sort,
            order: urutan.order,
            limit: PER_HALAMAN,
            offset: halaman * PER_HALAMAN,
          }),
        ]);
        if (dibatalkan) return;

        setData(dashboard);
        setHistory(halamanHasil.items);
        setTotal(halamanHasil.total);
        setError(null);
      } catch (err) {
        if (!dibatalkan) {
          setError(err instanceof ApiError ? err.message : "Data failed to load.");
        }
      } finally {
        if (!dibatalkan) setMemuat(false);
      }
    })();
    return () => {
      dibatalkan = true;
    };
  }, [kunci, urutan, halaman]);

  /** Citra diambil di sini — bukan saat daftar dimuat.
   *
   *  Inilah yang menjaga daftar tetap ringan berapa pun banyaknya citra: satu
   *  berkas diunduh ketika satu baris dipilih, bukan seluruhnya di muka. */
  async function pilihCitra(item: ResultListItem) {
    if (item.image_id === result?.image_id) return;
    if (item.status !== "analyzed") {
      setResult(null);
      setHighlighted(null);
      return;
    }
    setMemuatCitra(true);
    try {
      setResult(await getResult(item.image_id));
      setHighlighted(null);
    } catch {
      /* panel tetap menampilkan citra sebelumnya */
    } finally {
      setMemuatCitra(false);
    }
  }

  function ubahUrutan(kolom: ResultSort) {
    setUrutan((sekarang) =>
      sekarang.sort === kolom
        ? { sort: kolom, order: sekarang.order === "asc" ? "desc" : "asc" }
        : // Kolom teks paling berguna menaik; kolom angka dan tanggal paling
          // berguna menurun — terbaru dan terbanyak lebih dulu.
          { sort: kolom, order: kolom === "label" ? "asc" : "desc" },
    );
  }

  const halamanTerakhir = Math.max(0, Math.ceil(total / PER_HALAMAN) - 1);

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
            OPERATIONS DASHBOARD
          </div>
          <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
            Plant Condition Analysis
          </h1>
        </div>
        <div className="flex items-center gap-[10px]">
          <span className="mono hidden rounded-[11px] border border-[var(--line)] bg-[var(--card)] px-[14px] py-[10px] text-[11px] text-[var(--muted-3)] sm:block">
            {data ? `${data.images_analyzed}/${data.images_total} images analysed` : "loading…"}
          </span>
          <Link
            href="/upload"
            className="kartu-tekan rounded-[11px] bg-[var(--brand)] px-[18px] py-[11px] text-[12.5px] font-bold text-white"
          >
            Upload &amp; Analyse
          </Link>
        </div>
      </header>

      {data?.images_analyzed === 0 && !kunci && (
        <div className="muncul rounded-[12px] border border-[#bfe6d7] bg-[var(--green-bg)] px-4 py-3 text-[12.5px] text-[var(--green-d)]">
          No image has been analysed yet.{" "}
          <Link href="/upload" className="font-bold underline">
            Upload your first image
          </Link>{" "}
          to fill this dashboard.
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
          placeholder="Search image label…"
          aria-label="Search image label"
          className="w-full rounded-[11px] border border-[var(--line)] bg-[var(--card)] py-[10px] pl-[36px] pr-[34px] text-[12.5px] outline-none transition focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_rgba(47,191,113,.14)]"
        />
        {cari && (
          <button
            onClick={() => setCari("")}
            aria-label="Clear search"
            className="absolute right-[10px] top-1/2 -translate-y-1/2 rounded-full px-[6px] text-[15px] leading-none text-[var(--muted-3)] hover:text-[var(--ink)]"
          >
            ×
          </button>
        )}
      </div>

      {/* --- Angka ringkas ---
           Empat kelas kondisi, bukan sehat/bermasalah/berat. Kelompok yang lama
           saling beririsan — "berat" adalah bagian dari "bermasalah" — sehingga
           ketiga persentasenya tidak berjumlah 100% dan mudah salah dibaca.
           Keempat kelas ini saling lepas: dari 100 pohon, sekian sehat, sekian
           menguning, sekian kerdil, sekian mati. --- */}
      {memuat || !data || !summary ? (
        <KerangkaAngka />
      ) : (
        <section className="flex flex-col gap-[14px]">
          <div className="muncul flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-[13px] font-semibold text-[var(--muted)]">
              Of
            </span>
            <span className="text-[26px] font-extrabold tracking-[-0.03em] text-[var(--ink)]">
              {summary.total.toLocaleString("en-GB")}
            </span>
            <span className="text-[13px] font-semibold text-[var(--muted)]">
              trees detected across {data.images_analyzed} image
              {data.images_analyzed === 1 ? "" : "s"}:
            </span>
          </div>

          <div className="grid grid-cols-2 gap-[14px] xl:grid-cols-4">
            {data.by_condition.map((item, i) => (
              <div key={item.label} className="muncul" style={{ ["--i" as string]: i }}>
                <StatCard
                  label={item.label}
                  value={item.count}
                  share={share(item.count)}
                  note={`${(share(item.count) * 100).toFixed(1)}% of all trees`}
                  color={CONDITION_COLOR[item.label]}
                />
              </div>
            ))}
          </div>

          <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
            These four classes are mutually exclusive, so their percentages add
            up to 100%. Percentages are of trees the model <b>detected</b>, not
            of every tree in the field — anything the model missed is counted
            nowhere.
          </p>
        </section>
      )}

      {/* --- Pemilih citra + panel hasil --- */}
      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <div className="muncul" style={{ ["--i" as string]: 2 }}>
          <Card
            title="Scanned Images"
            subtitle={
              total > 0
                ? `${total} images · click a row to open its result`
                : "Click a row to open its result"
            }
            action={
              <Link
                href="/detections"
                className="text-[11.5px] font-bold text-[var(--brand-2)]"
              >
                All images →
              </Link>
            }
          >
            <ResultTable
              items={history}
              urutan={urutan}
              onUrut={ubahUrutan}
              selectedId={result?.image_id ?? null}
              onSelect={pilihCitra}
              loading={memuat}
            />

            {halamanTerakhir > 0 && (
              <div className="flex items-center justify-between gap-3 border-t border-[var(--line-soft)] pt-3">
                <span className="mono text-[11px] text-[var(--muted-3)]">
                  {halaman * PER_HALAMAN + 1}–
                  {Math.min((halaman + 1) * PER_HALAMAN, total)} of {total}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setHalaman((n) => Math.max(0, n - 1))}
                    disabled={halaman === 0 || memuat}
                    className="kartu-tekan rounded-[8px] border border-[var(--line)] px-[11px] py-[6px] text-[11.5px] font-semibold text-[var(--brand)] disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() =>
                      setHalaman((n) => Math.min(halamanTerakhir, n + 1))
                    }
                    disabled={halaman >= halamanTerakhir || memuat}
                    className="kartu-tekan rounded-[8px] border border-[var(--line)] px-[11px] py-[6px] text-[11.5px] font-semibold text-[var(--brand)] disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="muncul" style={{ ["--i" as string]: 3 }}>
          <DronePanel
            result={result}
            highlighted={highlighted}
            onHighlight={setHighlighted}
            loading={memuatCitra}
          />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <div className="muncul" style={{ ["--i" as string]: 4 }}>
          <Card title="Condition Distribution">
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
          <Card title="Healthy vs Affected">
            {memuat || !summary ? (
              <div className="kerangka h-[190px]" />
            ) : (
              <HealthDonut healthy={summary.healthy} affected={summary.infected} />
            )}
          </Card>
        </div>
      </section>

      <section className="muncul grid gap-4" style={{ ["--i" as string]: 6 }}>
        <Card title="Inference Queue" subtitle="Images entering the system">
          <InferenceQueue items={history} />
        </Card>
      </section>
    </>
  );
}
