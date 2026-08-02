"use client";

import { SEVERITY_COLOR } from "@/lib/severity";
import type { NamedCount } from "@/types/detection";

const BAR_COLORS: Record<string, string> = {
  Sehat: "var(--chart-1)",
  Menguning: "var(--chart-3)",
  "Mati/stres": "var(--chart-4)",
  Kerdil: "var(--chart-2)",
};

/** Horizontal bars with a share-of-total figure, one row per condition. */
export function ConditionBars({ items }: { items: NamedCount[] }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  if (total === 0) {
    return (
      <p className="text-[12.5px] text-[var(--muted)]">
        Belum ada data. Analisis sebuah citra terlebih dahulu.
      </p>
    );
  }

  return (
    <div className="space-y-[14px]">
      {items.map((item) => {
        const percent = (item.count / total) * 100;
        return (
          <div key={item.label} className="flex items-center gap-3 text-[12.5px]">
            <div className="w-[92px] flex-shrink-0 text-right text-[var(--muted)]">
              {item.label}
            </div>
            <div className="h-[18px] flex-1 overflow-hidden rounded-[5px] bg-[var(--page)]">
              <div
                className="flex h-full items-center justify-end rounded-[5px] pr-2 text-[10.5px] font-semibold text-white"
                style={{
                  width: `${Math.max(percent, 7)}%`,
                  background: BAR_COLORS[item.label] ?? "var(--chart-2)",
                }}
              >
                {percent.toFixed(0)}%
              </div>
            </div>
            <div className="w-[52px] text-right tabular-nums text-[var(--muted)]">
              {item.count}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Ring chart: healthy versus everything that needs attention. */
export function HealthDonut({
  healthy,
  affected,
}: {
  healthy: number;
  affected: number;
}) {
  const total = healthy + affected;
  const percent = total > 0 ? (affected / total) * 100 : 0;

  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg width="148" height="148" viewBox="0 0 42 42" aria-hidden>
        <circle
          cx="21"
          cy="21"
          r="15.9155"
          fill="none"
          stroke={SEVERITY_COLOR.sehat}
          strokeWidth="5.5"
        />
        <circle
          cx="21"
          cy="21"
          r="15.9155"
          fill="none"
          stroke="var(--chart-4)"
          strokeWidth="5.5"
          strokeDasharray={`${percent} ${100 - percent}`}
          strokeDashoffset="25"
          transform="rotate(-90 21 21)"
        />
        <text
          x="21"
          y="20.4"
          textAnchor="middle"
          fontSize="6.5"
          fontWeight="700"
          fill="var(--green-d)"
        >
          {percent.toFixed(0)}%
        </text>
        <text x="21" y="26" textAnchor="middle" fontSize="3.2" fill="var(--muted)">
          bermasalah
        </text>
      </svg>

      <ul className="space-y-[10px] text-[12.5px]">
        <li className="flex items-center gap-[10px]">
          <i
            className="h-[10px] w-[10px] rounded-full"
            style={{ background: SEVERITY_COLOR.sehat }}
          />
          Sehat — <b>{healthy.toLocaleString("id-ID")}</b> pohon
        </li>
        <li className="flex items-center gap-[10px]">
          <i
            className="h-[10px] w-[10px] rounded-full"
            style={{ background: "var(--chart-4)" }}
          />
          Bermasalah — <b>{affected.toLocaleString("id-ID")}</b> pohon
        </li>
      </ul>
    </div>
  );
}
