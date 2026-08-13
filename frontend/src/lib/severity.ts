import type { Severity } from "@/types/detection";

/** Colour per severity, from the client's redesign palette. */
export const SEVERITY_COLOR: Record<Severity, string> = {
  sehat: "#2FBF71",
  ringan: "#E8B93B",
  sedang: "#E8B93B",
  berat: "#E2574C",
};

/** Background/foreground pair for the severity badge. */
export const SEVERITY_BADGE: Record<Severity, { bg: string; fg: string }> = {
  sehat: { bg: "rgba(47,191,113,.12)", fg: "#0F8A55" },
  ringan: { bg: "rgba(232,185,59,.16)", fg: "#8A6A11" },
  sedang: { bg: "rgba(232,185,59,.16)", fg: "#8A6A11" },
  berat: { bg: "rgba(226,87,76,.12)", fg: "#B8362C" },
};

/** Map layers, matching the redesign's three-colour legend. */
export const LAYERS: {
  key: "sehat" | "ringan" | "berat";
  label: string;
  color: string;
  covers: Severity[];
}[] = [
  { key: "sehat", label: "Green (Healthy)", color: "#2FBF71", covers: ["sehat"] },
  {
    key: "ringan",
    label: "Amber (Mild–moderate)",
    color: "#E8B93B",
    covers: ["ringan", "sedang"],
  },
  { key: "berat", label: "Red (Severe)", color: "#E2574C", covers: ["berat"] },
];

/** The three groups the legend shows. */
export const LEGEND = LAYERS.map(({ label, color }) => ({ label, color }));

export function isHealthy(severity: Severity): boolean {
  return severity === "sehat";
}

/** Which layer a severity belongs to. */
export function layerOf(severity: Severity): "sehat" | "ringan" | "berat" {
  if (severity === "sehat") return "sehat";
  if (severity === "berat") return "berat";
  return "ringan";
}

/** Nama keparahan yang ditampilkan.
 *
 * Nilai `sehat`/`ringan`/`sedang`/`berat` adalah DATA yang tersimpan di
 * database dan dipakai sebagai kunci di seluruh aplikasi. Menerjemahkan
 * nilainya berarti memigrasikan setiap baris deteksi dan menyentuh aturan
 * keparahan di backend; menerjemahkan hanya saat ditampilkan tidak menyentuh
 * data sama sekali. */
export const SEVERITY_LABEL: Record<Severity, string> = {
  sehat: "Healthy",
  ringan: "Mild",
  sedang: "Moderate",
  berat: "Severe",
};
