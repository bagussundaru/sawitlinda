"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, uploadImages } from "@/lib/api";

const ACCEPT = ".jpg,.jpeg,.png,.tif,.tiff";

export default function UnggahPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [names, setNames] = useState<string[]>([]);

  async function send(files: File[]) {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    setNames(files.map((file) => file.name));
    try {
      const { images } = await uploadImages(files);
      router.push(`/proses?ids=${images.map((i) => i.image_id).join(",")}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unggahan gagal. Coba lagi.");
      setBusy(false);
      setNames([]);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-[18px]">
      <div>
        <h1 className="text-[19px] font-bold">Unggah Citra UAV</h1>
        <p className="text-[13px] text-[var(--muted)]">
          Unggah foto hasil drone perkebunan. Koordinat GPS diambil otomatis dari
          metadata bila tersedia.
        </p>
      </div>

      <Card>
        <div
          role="button"
          tabIndex={0}
          aria-busy={busy}
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
            if (!busy) void send(Array.from(event.dataTransfer.files));
          }}
          className={`cursor-pointer rounded-[12px] border-2 border-dashed px-5 py-12 text-center transition ${
            busy ? "cursor-wait opacity-70" : ""
          } ${
            dragging
              ? "border-[var(--green)] bg-[#d3efe5]"
              : "border-[var(--green-l)] bg-[var(--green-bg)] hover:bg-[#d9f0e7]"
          }`}
        >
          <div className="text-[40px] leading-none">{busy ? "⏳" : "☁️"}</div>
          <h3 className="mb-1 mt-3 text-[15px] font-semibold text-[var(--green-d)]">
            {busy ? "Mengunggah…" : "Tarik & letakkan citra di sini"}
          </h3>
          <p className="text-[12.5px] text-[var(--muted)]">
            atau klik untuk memilih file · JPG / PNG / TIFF · single atau batch
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(event) => {
              void send(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
          />
        </div>

        {names.length > 0 && (
          <ul className="mt-4 space-y-1 text-[12.5px] text-[var(--muted)]">
            {names.map((name) => (
              <li key={name}>📄 {name}</li>
            ))}
          </ul>
        )}

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-[15px] py-3 text-[12.5px] text-[var(--red)]"
          >
            {error}
          </p>
        )}
      </Card>

      <div className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-[15px] py-3 text-[12.5px] text-[var(--green-d)]">
        💡 Peta sebaran hanya terisi bila citra membawa koordinat GPS di metadata
        EXIF — foto drone asli yang belum diedit ulang.
      </div>
    </div>
  );
}
