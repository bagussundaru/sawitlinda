"use client";

import type { TrainingPoint } from "@/types/detection";

export interface Seri {
  key: keyof TrainingPoint;
  label: string;
  color: string;
}

const W = 520;
const H = 190;
const PAD = { atas: 12, kanan: 10, bawah: 24, kiri: 38 };

/** Grafik garis untuk metrik per epoch.
 *
 * Digambar sebagai SVG, bukan lewat pustaka grafik: sisa aplikasi sudah memakai
 * cara ini, dan menambah pustaka hanya untuk satu layar akan membesarkan bundel
 * tanpa imbalan yang setara.
 *
 * viewBox membuatnya ikut melebar mengikuti kolom, jadi tinggi & lebar di sini
 * hanya menentukan perbandingan sisi, bukan ukuran akhir.
 */
export default function TrainingChart({
  points,
  series,
  yMax,
  title,
}: {
  points: TrainingPoint[];
  series: Seri[];
  /** Batas atas sumbu Y. Kosongkan agar dihitung dari data. */
  yMax?: number;
  title: string;
}) {
  const bernilai = (p: TrainingPoint, k: keyof TrainingPoint) => {
    const v = p[k];
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  };

  const semua = points.flatMap((p) =>
    series.map((s) => bernilai(p, s.key)).filter((v): v is number => v !== null),
  );
  const atas = yMax ?? (semua.length ? Math.max(...semua) * 1.15 : 1);
  const maxEpoch = Math.max(points.at(-1)?.epoch ?? 1, 2);

  const x = (epoch: number) =>
    PAD.kiri + ((epoch - 1) / (maxEpoch - 1)) * (W - PAD.kiri - PAD.kanan);
  const y = (nilai: number) =>
    H - PAD.bawah - (atas > 0 ? nilai / atas : 0) * (H - PAD.atas - PAD.bawah);

  /** Titik tanpa nilai memutus garis, tidak dijembatani: menyambungkannya
   *  akan menggambar tren yang tidak pernah diukur. */
  const jalur = (s: Seri) => {
    const potongan: string[] = [];
    let menyambung = false;
    for (const p of points) {
      const v = bernilai(p, s.key);
      if (v === null) {
        menyambung = false;
        continue;
      }
      potongan.push(`${menyambung ? "L" : "M"}${x(p.epoch).toFixed(1)},${y(v).toFixed(1)}`);
      menyambung = true;
    }
    return potongan.join(" ");
  };

  const garisY = [0, 0.25, 0.5, 0.75, 1].map((f) => f * atas);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12.5px] font-bold text-[var(--ink)]">{title}</span>
        <div className="flex flex-wrap gap-3">
          {series.map((s) => (
            <span
              key={String(s.key)}
              className="flex items-center gap-[5px] text-[11px] text-[var(--muted)]"
            >
              <span
                className="h-[3px] w-[13px] rounded-full"
                style={{ background: s.color }}
              />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`${title} per epoch`}
      >
        {garisY.map((nilai) => (
          <g key={nilai}>
            <line
              x1={PAD.kiri}
              x2={W - PAD.kanan}
              y1={y(nilai)}
              y2={y(nilai)}
              stroke="var(--line-soft)"
              strokeWidth={1}
            />
            <text
              x={PAD.kiri - 6}
              y={y(nilai) + 3}
              textAnchor="end"
              className="mono"
              fontSize="9"
              fill="var(--muted-3)"
            >
              {atas >= 10 ? nilai.toFixed(0) : nilai.toFixed(2)}
            </text>
          </g>
        ))}

        <text
          x={PAD.kiri}
          y={H - 6}
          fontSize="9"
          className="mono"
          fill="var(--muted-3)"
        >
          1
        </text>
        <text
          x={W - PAD.kanan}
          y={H - 6}
          textAnchor="end"
          fontSize="9"
          className="mono"
          fill="var(--muted-3)"
        >
          epoch {maxEpoch}
        </text>

        {series.map((s) => (
          <path
            key={String(s.key)}
            d={jalur(s)}
            fill="none"
            stroke={s.color}
            strokeWidth={1.9}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {/* Titik terakhir ditandai supaya nilai terkini mudah ditemukan. */}
        {series.map((s) => {
          const terakhir = [...points].reverse().find((p) => bernilai(p, s.key) !== null);
          if (!terakhir) return null;
          return (
            <circle
              key={`titik-${String(s.key)}`}
              cx={x(terakhir.epoch)}
              cy={y(bernilai(terakhir, s.key) as number)}
              r={3}
              fill={s.color}
            />
          );
        })}
      </svg>
    </div>
  );
}
