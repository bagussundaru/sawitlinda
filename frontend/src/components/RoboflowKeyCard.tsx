"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/Card";
import {
  ApiError,
  clearRoboflowKey,
  getRoboflowSettings,
  saveRoboflowKey,
} from "@/lib/api";
import type { RoboflowSettings } from "@/types/detection";

/** Roboflow API key.
 *
 * Sent once and never readable again — the API returns only its status and the
 * last four characters, the same rule as the Nebius key. */
export default function RoboflowKeyCard() {
  const [status, setStatus] = useState<RoboflowSettings | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRoboflowSettings()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  async function save() {
    if (key.trim().length < 8) {
      setError("Key is too short.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setStatus(await saveRoboflowKey(key.trim()));
      setKey("");
      setMessage("Key saved and effective immediately.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the key.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setStatus(await clearRoboflowKey());
      setMessage("Key removed from the application.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the key.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Roboflow API key"
      subtitle="Lets Evaluation pull dataset versions without uploading files"
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
            {status.key_hint}
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
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Paste your Roboflow private API key"
            className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[9px] font-mono text-[12px] outline-none focus:border-[var(--accent)]"
          />
        </label>

        <button
          onClick={save}
          disabled={busy}
          className="rounded-[10px] bg-[var(--brand)] px-4 py-[10px] text-[12.5px] font-bold text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save"}
        </button>

        {status?.configured && (
          <button
            onClick={remove}
            disabled={busy}
            className="rounded-[10px] border border-[var(--line)] px-4 py-[10px] text-[12.5px] font-semibold text-[var(--red)] disabled:opacity-60"
          >
            Delete
          </button>
        )}
      </div>

      {message && (
        <p className="rounded-[10px] border border-[#bfe6d7] bg-[var(--green-bg)] px-3 py-[10px] text-[12px] text-[var(--green-d)]">
          {message}
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

      <p className="text-[11px] leading-relaxed text-[var(--muted-3)]">
        Found in Roboflow under Settings → API Keys (the <b>private</b> key).
        It is stored on the server and takes effect immediately. Once sent, it
        can never be read back through the application — only its last four
        characters are shown.
      </p>
    </Card>
  );
}
