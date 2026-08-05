"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, listBlocks, uploadImages } from "@/lib/api";
import type { BlockInfo } from "@/types/detection";

const ACCEPT = ".jpg,.jpeg,.png,.tif,.tiff";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-[6px]">
      <span className="text-[12px] font-semibold text-[var(--muted)]">{label}</span>
      {children}
      {hint && <span className="text-[10.5px] text-[var(--muted-3)]">{hint}</span>}
    </label>
  );
}

const inputClass =
  "rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] text-[13px] outline-none focus:border-[var(--accent)]";

export default function UnggahPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [block, setBlock] = useState("");
  const [areaHa, setAreaHa] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [knownBlocks, setKnownBlocks] = useState<BlockInfo[]>([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBlocks()
      .then((blocks) => setKnownBlocks(blocks.filter((b) => b.block)))
      .catch(() => setKnownBlocks([]));
  }, []);

  async function submit() {
    if (files.length === 0) {
      setError("Pilih dulu citra yang akan diunggah.");
      return;
    }
    if ((lat.trim() === "") !== (lng.trim() === "")) {
      setError("Lintang dan bujur harus diisi berpasangan.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const { images } = await uploadImages(files, { block, areaHa, lat, lng });
      router.push(`/proses?ids=${images.map((i) => i.image_id).join(",")}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unggahan gagal. Coba lagi.");
      setBusy(false);
    }
  }

  return (
    <>
      <header>
        <div className="text-[11px] font-bold tracking-[0.15em] text-[#5c7a6b]">
          MASUKKAN DATA
        </div>
        <h1 className="mt-[5px] text-[29px] font-extrabold tracking-[-0.035em]">
          Unggah Citra UAV
        </h1>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card
          title="Berkas citra"
          subtitle="JPG / PNG / TIFF · satu atau beberapa sekaligus"
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
              setFiles(Array.from(event.dataTransfer.files));
            }}
            className={`cursor-pointer rounded-[14px] border-2 border-dashed px-5 py-10 text-center transition ${
              dragging
                ? "border-[var(--accent)] bg-[#dff2e7]"
                : "border-[#b6d9c4] bg-[#f1f8f3] hover:bg-[#e7f4ec]"
            }`}
          >
            <div className="text-[34px] leading-none">☁️</div>
            <h3 className="mb-1 mt-3 text-[14px] font-bold text-[var(--brand)]">
              Tarik &amp; letakkan citra di sini
            </h3>
            <p className="text-[12px] text-[var(--muted-2)]">
              atau klik untuk memilih berkas
            </p>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(event) => {
                setFiles(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
          </div>

          {files.length > 0 && (
            <ul className="space-y-1 text-[12px] text-[var(--muted)]">
              {files.map((file) => (
                <li key={file.name} className="flex justify-between gap-3">
                  <span className="truncate">📄 {file.name}</span>
                  <span className="mono flex-none text-[11px] text-[var(--muted-3)]">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Keterangan citra"
          subtitle="Tidak bisa disimpulkan dari berkasnya, jadi diisi di sini"
        >
          <Field label="Blok kebun" hint="Misal A-3. Dipakai untuk mengelompokkan hasil.">
            <input
              className={inputClass}
              list="blok-dikenal"
              value={block}
              onChange={(event) => setBlock(event.target.value)}
              placeholder="A-3"
            />
            <datalist id="blok-dikenal">
              {knownBlocks.map((item) => (
                <option key={item.block} value={item.block ?? ""} />
              ))}
            </datalist>
          </Field>

          <Field
            label="Luas area tercakup (ha)"
            hint="Wajib diisi agar titik pohon muncul di peta — dari luas inilah skala tanah (meter per piksel) dihitung."
          >
            <input
              className={inputClass}
              type="number"
              min="0"
              step="0.1"
              value={areaHa}
              onChange={(event) => setAreaHa(event.target.value)}
              placeholder="4.5"
            />
          </Field>

          <div>
            <div className="mb-[6px] text-[12px] font-semibold text-[var(--muted)]">
              Titik koordinat
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                className={inputClass}
                value={lat}
                onChange={(event) => setLat(event.target.value)}
                placeholder="Lintang −0.78912"
              />
              <input
                className={inputClass}
                value={lng}
                onChange={(event) => setLng(event.target.value)}
                placeholder="Bujur 101.41233"
              />
            </div>
            <p className="mt-[6px] text-[10.5px] leading-relaxed text-[var(--muted-3)]">
              Kosongkan bila citra membawa GPS di EXIF — metadata asli selalu
              dipakai lebih dulu, isian ini hanya menambal bila EXIF kosong.
              Tanpa koordinat, citra tetap dianalisis tapi tidak muncul di peta.
            </p>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
            >
              {error}
            </p>
          )}

          <button
            onClick={submit}
            disabled={busy}
            className="rounded-[11px] bg-[var(--brand)] px-5 py-[12px] text-[13px] font-bold text-white disabled:opacity-60"
          >
            {busy ? "Mengunggah…" : `Unggah & Analisis${files.length ? ` (${files.length})` : ""}`}
          </button>
        </Card>
      </div>
    </>
  );
}
