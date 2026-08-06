"use client";

import { useState } from "react";

import { ApiError, login } from "@/lib/api";

/** Layar masuk. Ditampilkan menggantikan seluruh aplikasi selama belum ada sesi.
 *
 * Digabung ke AppShell, bukan halaman tersendiri dengan pengalihan: pengalihan
 * membuat isi halaman sempat terlihat sekejap sebelum berpindah. */
export default function LoginScreen({
  ready,
  onSuccess,
}: {
  /** False berarti server belum punya akun sama sekali. */
  ready: boolean;
  onSuccess: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function kirim(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal masuk.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--sidebar)] px-5 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-7 flex items-center gap-3">
          <span
            className="flex h-[42px] w-[42px] items-center justify-center rounded-[13px] text-[18px] font-extrabold text-[#04231a]"
            style={{ background: "linear-gradient(145deg,#2FBF71,#0F8A55)" }}
          >
            S
          </span>
          <span>
            <span className="block text-[19px] font-extrabold tracking-[-0.02em] text-white">
              SawitScan AI
            </span>
            <span className="block text-[10px] font-semibold tracking-[0.16em] text-[var(--sidebar-sub)]">
              UAV PLANT INTEL
            </span>
          </span>
        </div>

        {!ready ? (
          <div className="rounded-[16px] border border-[#e5cfa6]/30 bg-[#3a2f16] p-6 text-[13px] leading-relaxed text-[#f0d79a]">
            <b className="mb-2 block text-white">Belum ada akun terdaftar</b>
            Aplikasi tidak dapat dipakai sampai akun pertama dibuat. Jalankan di
            server:
            <code className="mono mt-3 block rounded-[8px] bg-black/30 px-3 py-2 text-[11.5px] text-[#9fe3c0]">
              docker compose exec backend python scripts/create_user.py
            </code>
          </div>
        ) : (
          <form
            onSubmit={kirim}
            className="flex flex-col gap-4 rounded-[16px] bg-[var(--card)] p-6 shadow-[0_18px_50px_rgba(0,0,0,.28)]"
          >
            <div>
              <h1 className="text-[17px] font-extrabold tracking-[-0.01em] text-[var(--ink)]">
                Masuk
              </h1>
              <p className="mt-1 text-[12px] text-[var(--muted)]">
                Diperlukan untuk seluruh fitur, termasuk training model.
              </p>
            </div>

            <label className="flex flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Nama pengguna
              </span>
              <input
                autoFocus
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[10px] text-[13px] outline-none focus:border-[var(--accent)]"
              />
            </label>

            <label className="flex flex-col gap-[6px]">
              <span className="text-[12px] font-semibold text-[var(--muted)]">
                Kata sandi
              </span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-[10px] border border-[var(--line)] bg-white px-3 py-[10px] text-[13px] outline-none focus:border-[var(--accent)]"
              />
            </label>

            {error && (
              <p
                role="alert"
                className="rounded-[10px] border border-[#f0c9c9] bg-[var(--red-bg)] px-3 py-[10px] text-[12px] text-[var(--red)]"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy || !username || !password}
              className="rounded-[10px] bg-[var(--brand)] px-4 py-[11px] text-[13px] font-bold text-white disabled:opacity-50"
            >
              {busy ? "Memeriksa…" : "Masuk"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
