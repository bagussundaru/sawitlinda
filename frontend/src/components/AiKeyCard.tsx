"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import {
  ApiError,
  clearAiKey,
  getAiSettings,
  saveAiKey,
  saveAiModel,
} from "@/lib/api";
import type { AiSettings } from "@/types/detection";

/** Form pengisian kunci API Nebius.
 *
 * Kunci dikirim sekali lalu tidak pernah dapat dibaca kembali — API hanya
 * mengembalikan status dan empat karakter terakhir sebagai penanda. */
export default function AiKeyCard() {
  const [status, setStatus] = useState<AiSettings | null>(null);
  const [kunci, setKunci] = useState("");
  const [model, setModel] = useState("");
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
      setError("Key is too short.");
      return;
    }
    setBusy(true);
    setError(null);
    setPesan(null);
    try {
      setStatus(await saveAiKey(kunci.trim(), model));
      setKunci("");
      setModel("");
      setPesan("Key saved and effective immediately.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the key.");
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
      setPesan("Key removed from the application.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the key.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Nebius API key"
      subtitle="For the AI Review feature on the detection result screen"
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
          {status?.configured ? "Active" : "Not set"}
        </span>
        {status?.configured && (
          <span className="mono text-[11px] text-[var(--muted-3)]">
            {status.key_hint} · set via {status.source} · {status.model}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-[260px] flex-1 flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            {status?.configured ? "Replace key" : "API key"}
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

        <label className="flex min-w-[240px] flex-1 flex-col gap-[6px]">
          <span className="text-[12px] font-semibold text-[var(--muted)]">
            Model (optional)
          </span>
          <input
            autoComplete="off"
            spellCheck={false}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={status?.model ?? "Qwen/Qwen2-VL-72B-Instruct"}
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <button
          onClick={simpan}
          disabled={busy}
          className="rounded-[10px] bg-[var(--brand)] px-4 py-[10px] text-[12.5px] font-bold text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save"}
        </button>

        {status?.configured && (
          <button
            onClick={async () => {
              if (!model.trim()) {
                setError("Enter a model name first.");
                return;
              }
              setBusy(true);
              setError(null);
              try {
                setStatus(await saveAiModel(model.trim()));
                setModel("");
                setPesan("Model changed.");
              } catch (err) {
                setError(err instanceof ApiError ? err.message : "Could not change the model.");
              } finally {
                setBusy(false);
              }
            }}
            disabled={busy}
            className="rounded-[10px] border border-[var(--line)] px-4 py-[10px] text-[12.5px] font-semibold text-[var(--brand)] disabled:opacity-60"
          >
            Change model only
          </button>
        )}

        {status?.source === "aplikasi" && (
          <button
            onClick={hapus}
            disabled={busy}
            className="rounded-[10px] border border-[var(--line)] px-4 py-[10px] text-[12.5px] font-semibold text-[var(--red)] disabled:opacity-60"
          >
            Delete
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
        <b>This application has no authentication yet.</b> Until it does, anyone
        who can open its address can replace the key here and spend your
        Nebius quota. Restrict access at the reverse proxy until authentication
        is built.
      </div>

      <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
        Not every model accepts images. If the chosen model takes text only
        — DeepSeek and most language models — a review is still produced,
        but from the <b>detection summary</b>, not from the image. Such results
        are marked clearly so the difference is never hidden.
      </p>

      <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
        The key is stored on the server and takes effect immediately. Once
        sent, it can never be read back through the application — only
        its last four characters are shown.
      </p>
    </Card>
  );
}
