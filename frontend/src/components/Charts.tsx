"use client";

import type { NamedCount } from "@/types/detection";

const BAR_COLORS: Record<string, string> = {
  Sehat: "linear-gradient(90deg,#2FBF71,#0F8A55)",
  Menguning: "linear-gradient(90deg,#F0CB63,#E8B93B)",
  "Mati/stres": "linear-gradient(90deg,#EC7A71,#E2574C)",
  Kerdil: "linear-gradient(90deg,#8FD3AC,#4FA37B)",
};

/** One row per condition, click to focus that condition on the map. */
export function ConditionBars({
  items,
  focused,
  onFocus,
}: {
  items: NamedCount[];
  focused?: string | null;
  onFocus?: (label: string | null) => void;
}) {
  const total = items.reduce((sum, item) => sum + item.count, 0);

  if (total === 0) {
    return (
      <p className="text-[12.5px] text-[var(--muted-2)]">
        No data yet. Analyse an image first.
      </p>
    );
  }

  return (
    <>
      {items.map((item) => {
        const percent = (item.count / total) * 100;
        const active = focused === item.label;
        return (
          <div
            key={item.label}
            onClick={() => onFocus?.(active ? null : item.label)}
            className="flex cursor-pointer items-center gap-[14px]"
          >
            <div className="w-[132px] text-[12.5px] font-semibold">
              {item.label}
            </div>
            <div className="h-[9px] flex-1 overflow-hidden rounded-[6px] bg-[#F0F4F1]">
              <div
                className="h-full rounded-[6px] transition-[width] duration-300"
                style={{
                  width: `${Math.max(percent, 3)}%`,
                  background: active
                    ? "var(--brand)"
                    : BAR_COLORS[item.label] ?? "var(--accent)",
                }}
              />
            </div>
            <div className="mono w-[78px] text-right text-[11.5px] text-[#4b6656]">
              {percent.toFixed(0)}% · {item.count}
            </div>
          </div>
        );
      })}
      {onFocus && (
        <p className="mt-1 text-[11.5px] text-[var(--muted-2)]">
          Click a row to highlight that condition.
        </p>
      )}
    </>
  );
}

/** Healthy versus everything needing attention. */
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
      <svg width="140" height="140" viewBox="0 0 42 42" aria-hidden>
        <circle cx="21" cy="21" r="15.9155" fill="none" stroke="#2FBF71" strokeWidth="5.5" />
        <circle
          cx="21"
          cy="21"
          r="15.9155"
          fill="none"
          stroke="#E2574C"
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
          fontWeight="800"
          fill="#12261C"
        >
          {percent.toFixed(0)}%
        </text>
        <text x="21" y="26" textAnchor="middle" fontSize="3.2" fill="#65806F">
          affected
        </text>
      </svg>

      <ul className="space-y-[10px] text-[12.5px]">
        <li className="flex items-center gap-[10px]">
          <i className="h-[10px] w-[10px] rounded-full" style={{ background: "#2FBF71" }} />
          Healthy — <b>{healthy.toLocaleString("en-US")}</b> trees
        </li>
        <li className="flex items-center gap-[10px]">
          <i className="h-[10px] w-[10px] rounded-full" style={{ background: "#E2574C" }} />
          Affected — <b>{affected.toLocaleString("en-US")}</b> trees
        </li>
      </ul>
    </div>
  );
}
