"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import { ApiError, clearAiKey, getAiSettings, saveAiKey } from "@/lib/api";
import type { AiSettings } from "@/types/detection";

/** Form pengisian kunci API Nebius.
 *
 * Kunci dikirim sekali lalu tidak pernah dapat dibaca kembali — API hanya
 * mengembalikan status dan empat karakter terakhir sebagai penanda. */
export default function AiKeyCard() {
  const [status, setStatus] = useState<AiSettings | null>(null);
  const [kunci, setKunci] = useState("");
  const [busy, setBusy] = useState(false);
  const [pesan, setPesan] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAiSettings()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  async function simpan() {
    if (kunci.trim().length < 8) {
      setError("Kunci terlalu pendek.");
      return;
    }
    setBusy(true);
    setError(null);
    setPesan(null);
    try {
      setStatus(await saveAiKey(kunci.trim()));
      setKunci("");
      setPesan("Kunci tersimpan dan langsung berlaku.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyimpan kunci.");
    } finally {
      setBusy(false);
    }
  }

  async function hapus() {
    setBusy(true);
    setError(null);
    setPesan(null);
    try {
      setStatus(await clearAiKey());
      setPesan("Kunci dihapus dari aplikasi.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menghapus kunci.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Kunci API Nebius"
      subtitle="Untuk fitur Analisis AI pada layar hasil deteksi"
    >
      <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
        <span
          className="rounded-full px-[10px] py-[3px] text-[11px] font-bold"
          style={
            status?.configured
              ? { background: "rgba(47,191,113,.14)", color: "var(--brand-2)" }
              : { background: "var(--line-soft)", color: "var(--muted)" }
          }
        >
          {status?.configured ? "Aktif" : "Belum diisi"}
        </span>
        {status?.configured && (
          <span className="mono text-[11px] text-[var(--muted-3)]">
            {status.key_hint} · diisi lewat {status.source} · {status.model}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-[260px] flex-1 flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            {status?.configured ? "Ganti kunci" : "Kunci API"}
          </span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={kunci}
            onChange={(e) => setKunci(e.target.value)}
            placeholder="Tempel kunci Nebius di sini"
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <button
          onClick={simpan}
          disabled={busy}
          className="rounded-[10px] bg-[var(--brand)] px-4 py-[10px] text-[12.5px] font-bold text-white disabled:opacity-60"
        >
          {busy ? "Menyimpan…" : "Simpan"}
        </button>

        {status?.source === "aplikasi" && (
          <button
            onClick={hapus}
            disabled={busy}
            className="rounded-[10px] border border-[var(--line)] px-4 py-[10px] text-[12.5px] font-semibold text-[var(--red)] disabled:opacity-60"
          >
            Hapus
          </button>
        )}
      </div>

      {pesan && (
        <p className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-3 py-[10px] text-[12px] text-[var(--green-d)]">
          {pesan}
        </p>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
        >
          {error}
        </p>
      )}

      <div className="rounded-[10px] border border-[#e5cfa6] bg-[var(--amber-bg)] px-3 py-[10px] text-[11.5px] leading-relaxed text-[var(--amber)]">
        <b>Aplikasi ini belum punya autentikasi.</b> Selama itu belum ada, siapa
        pun yang bisa membuka alamatnya dapat mengganti kunci di sini dan memakai
        kuota Nebius Anda. Batasi aksesnya di reverse proxy sampai autentikasi
        dibangun.
      </div>

      <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
        Kunci disimpan di server dan berlaku seketika tanpa restart. Setelah
        dikirim, kunci tidak dapat dibaca kembali lewat aplikasi — yang
        ditampilkan hanya empat karakter terakhirnya.
      </p>
    </Card>
  );
}
