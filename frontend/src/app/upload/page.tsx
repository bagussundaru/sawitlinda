"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Card } from "@/components/Card";
import { listVillages, uploadImagesInBatches } from "@/lib/api";
import type { VillageInfo } from "@/types/detection";

const ACCEPT = ".jpg,.jpeg,.png,.tif,.tiff";

/** Satu berkas terpilih beserta label dan pratinjaunya. */
interface Antrean {
  file: File;
  label: string;
  preview: string;
  key: string;
}

/** Nama berkas tanpa ekstensi — tebakan awal yang masuk akal untuk label. */
function labelAwal(nama: string): string {
  return nama.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim() || nama;
}

function ukuran(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function UnggahPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [antrean, setAntrean] = useState<Antrean[]>([]);
  const [villages, setVillages] = useState<VillageInfo[]>([]);
  const [village, setVillage] = useState<string>("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progres, setProgres] = useState<{ done: number; total: number } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  // URL objek pratinjau dilepas saat komponen dibongkar; tanpa ini setiap
  // pemilihan berkas menahan memori gambar sampai halaman ditutup.
  useEffect(() => {
    return () => antrean.forEach((item) => URL.revokeObjectURL(item.preview));
    // Sengaja hanya saat unmount: pelepasan per-item ditangani hapus().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    listVillages()
      .then(setVillages)
      .catch(() => setVillages([]));
  }, []);

  function tambah(daftar: FileList | File[]) {
    const baru = Array.from(daftar).map((file, i) => ({
      file,
      label: labelAwal(file.name),
      preview: URL.createObjectURL(file),
      key: `${file.name}-${file.size}-${Date.now()}-${i}`,
    }));
    setAntrean((sekarang) => [...sekarang, ...baru]);
    setError(null);
  }

  function hapus(key: string) {
    setAntrean((sekarang) => {
      const item = sekarang.find((x) => x.key === key);
      if (item) URL.revokeObjectURL(item.preview);
      return sekarang.filter((x) => x.key !== key);
    });
  }

  function ubahLabel(key: string, nilai: string) {
    setAntrean((sekarang) =>
      sekarang.map((x) => (x.key === key ? { ...x, label: nilai } : x)),
    );
  }

  async function submit() {
    if (antrean.length === 0) {
      setError("Choose the images to upload first.");
      return;
    }
    setBusy(true);
    setError(null);
    setProgres({ done: 0, total: antrean.length });

    // Dikirim beberapa kali, bukan sekali: reverse proxy membatasi ukuran badan
    // permintaan, dan 100 bingkai UAV jauh melampaui batas itu.
    const { images, failedFrom, error: galat } = await uploadImagesInBatches(
      antrean.map((x) => ({ file: x.file, label: x.label })),
      setProgres,
      village || null,
    );

    if (failedFrom !== null) {
      // Yang sudah masuk tidak dibuang; sisanya tetap di antrean supaya dapat
      // dicoba lagi tanpa memilih ulang berkasnya.
      setAntrean((sekarang) => {
        sekarang.slice(0, failedFrom).forEach((x) => URL.revokeObjectURL(x.preview));
        return sekarang.slice(failedFrom);
      });
      setError(
        `${galat} ${images.length} images already went through; ${
          antrean.length - failedFrom
        } remain in the list and can be retried.`,
      );
      setBusy(false);
      setProgres(null);
      return;
    }

    router.push(`/processing?ids=${images.map((i) => i.image_id).join(",")}`);
  }

  return (
    <>
      <header className="muncul">
        <div className="text-[11px] font-bold tracking-[0.15em] text-[#5c7a6b]">
          DATA ENTRY
        </div>
        <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
          Upload &amp; Label
        </h1>
        <p className="mt-2 max-w-[560px] text-[13px] text-[var(--muted)]">
          Each image gets its own name. That name is what appears on the dashboard,
          in history, and in reports — so write something you will recognise later.
        </p>
      </header>

      <div className="muncul" style={{ ["--i" as string]: 1 }}>
        <Card
          title="Image files"
          subtitle="JPG / PNG / TIFF · one or many at once"
        >
          <div
            role="button"
            tabIndex={0}
            onClick={() => !busy && inputRef.current?.click()}
            onKeyDown={(event) => {
              if (!busy && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              tambah(event.dataTransfer.files);
            }}
            className={`cursor-pointer rounded-[14px] border-2 border-dashed px-5 py-10 text-center transition duration-200 ${
              dragging
                ? "scale-[1.01] border-[var(--accent)] bg-[#dff2e7] shadow-[0_0_0_4px_rgba(47,191,113,.12)]"
                : "border-[#b6d9c4] bg-[#f1f8f3] hover:bg-[#e7f4ec]"
            }`}
          >
            <div
              className={`text-[34px] leading-none transition-transform duration-300 ${
                dragging ? "-translate-y-1 scale-110" : ""
              }`}
            >
              ☁️
            </div>
            <h3 className="mb-1 mt-3 text-[14px] font-bold text-[var(--brand)]">
              {dragging ? "Drop them here" : "Drag & drop images here"}
            </h3>
            <p className="text-[12px] text-[var(--muted-2)]">
              or click to choose from your computer
            </p>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(event) => {
                if (event.target.files) tambah(event.target.files);
                event.target.value = "";
              }}
            />
          </div>

          {/* Desa berlaku untuk seluruh berkas pada unggahan ini: satu
              penerbangan UAV meliput satu wilayah. */}
          <label className="flex max-w-[380px] flex-col gap-[6px]">
            <span className="text-[12px] font-semibold text-[var(--muted)]">
              Village (optional)
            </span>
            <select
              value={village}
              onChange={(e) => setVillage(e.target.value)}
              disabled={busy}
              className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[12.5px] outline-none transition focus:border-[var(--accent)]"
            >
              <option value="">Not recorded</option>
              {villages.map((v) => (
                <option key={v.key} value={v.key}>
                  {v.name} · {v.district}
                </option>
              ))}
            </select>
            <span className="text-[10.5px] text-[var(--muted-3)]">
              Applies to every file in this upload. Used to group images on the
              map.
            </span>
          </label>

          {antrean.length > 0 && (
            <div className="flex flex-col gap-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-bold text-[var(--ink)]">
                  {antrean.length} images ready to upload
                </span>
                <button
                  onClick={() => {
                    antrean.forEach((x) => URL.revokeObjectURL(x.preview));
                    setAntrean([]);
                  }}
                  disabled={busy}
                  className="text-[11.5px] font-semibold text-[var(--red)] disabled:opacity-50"
                >
                  Clear all
                </button>
              </div>

              {antrean.map((item, i) => (
                <div
                  key={item.key}
                  style={{ ["--i" as string]: i }}
                  className="muncul flex items-center gap-3 rounded-[12px] border border-[var(--line)] bg-white p-[10px]"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={item.preview}
                    alt=""
                    className="h-[52px] w-[68px] shrink-0 rounded-[8px] object-cover"
                  />
                  <div className="flex min-w-0 flex-1 flex-col gap-[5px]">
                    <input
                      value={item.label}
                      onChange={(e) => ubahLabel(item.key, e.target.value)}
                      disabled={busy}
                      placeholder={item.file.name}
                      aria-label={`Label for ${item.file.name}`}
                      className="w-full rounded-[8px] border border-[var(--line)] bg-white px-[10px] py-[7px] text-[12.5px] font-semibold outline-none transition focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_rgba(47,191,113,.13)]"
                    />
                    <span className="mono truncate text-[10.5px] text-[var(--muted-3)]">
                      {item.file.name} · {ukuran(item.file.size)}
                    </span>
                  </div>
                  <button
                    onClick={() => hapus(item.key)}
                    disabled={busy}
                    aria-label={`Delete ${item.file.name}`}
                    className="shrink-0 rounded-[8px] px-[9px] py-[7px] text-[15px] leading-none text-[var(--muted-3)] transition hover:bg-[var(--red-bg)] hover:text-[var(--red)] disabled:opacity-40"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {error && (
            <p
              role="alert"
              className="muncul rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
            >
              {error}
            </p>
          )}

          <button
            onClick={submit}
            disabled={busy || antrean.length === 0}
            className="kartu-tekan flex items-center justify-center gap-2 rounded-[11px] bg-[var(--brand)] px-5 py-[12px] text-[13px] font-bold text-white disabled:opacity-50"
          >
            {busy ? (
              <>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="berputar"
                  aria-hidden
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="9"
                    stroke="currentColor"
                    strokeWidth="3"
                    opacity=".25"
                  />
                  <path
                    d="M21 12a9 9 0 0 0-9-9"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                  />
                </svg>
                {progres
                  ? `Uploading ${progres.done}/${progres.total}…`
                  : "Uploading…"}
              </>
            ) : (
              `Upload ${antrean.length || ""} images & analyse`.trim()
            )}
          </button>

          {busy && progres && (
            <div className="flex flex-col gap-[6px]">
              <div className="h-[7px] w-full overflow-hidden rounded-full bg-[var(--line-soft)]">
                <div
                  className="h-full rounded-full transition-[width] duration-300"
                  style={{
                    width: `${(progres.done / Math.max(1, progres.total)) * 100}%`,
                    background: "linear-gradient(90deg,#2FBF71,#0F8A55)",
                  }}
                />
              </div>
              <span className="mono text-[11px] text-[var(--muted-3)]">
                {progres.done} dari {progres.total} images sent
              </span>
            </div>
          )}

          <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
            Capture time is read from EXIF metadata when present. A label
            left empty falls back to the file name. Large uploads are sent
            in batches, so a network glitch only affects the last one.
          </p>
        </Card>
      </div>
    </>
  );
}
