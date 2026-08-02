import type { Severity } from "@/types/detection";

/** Colour per severity, taken from the prototype legend. */
export const SEVERITY_COLOR: Record<Severity, string> = {
  sehat: "#1D9E75",
  ringan: "#BA7517",
  sedang: "#BA7517",
  berat: "#A32D2D",
};

/** Background/foreground pair for the severity badge. */
export const SEVERITY_BADGE: Record<Severity, { bg: string; fg: string }> = {
  sehat: { bg: "var(--green-bg)", fg: "var(--green-d)" },
  ringan: { bg: "var(--amber-bg)", fg: "var(--amber)" },
  sedang: { bg: "var(--amber-bg)", fg: "var(--amber)" },
  berat: { bg: "var(--red-bg)", fg: "var(--red)" },
};

/** The three groups the prototype's legend shows. */
export const LEGEND: { label: string; color: string }[] = [
  { label: "Sehat", color: SEVERITY_COLOR.sehat },
  { label: "Terinfeksi ringan–sedang", color: SEVERITY_COLOR.ringan },
  { label: "Terinfeksi berat", color: SEVERITY_COLOR.berat },
];

export function isHealthy(severity: Severity): boolean {
  return severity === "sehat";
}
