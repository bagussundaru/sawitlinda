export function Card({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`flex flex-col gap-4 rounded-[18px] border border-[var(--line)] bg-[var(--card)] p-5 ${className}`}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-3">
          <div>
            {title && (
              <h3 className="text-[15px] font-extrabold tracking-[-0.02em]">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-[3px] text-[11.5px] text-[var(--muted-2)]">
                {subtitle}
              </p>
            )}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/** KPI tile: label, big figure, and a bar showing its share of the total. */
export function StatCard({
  label,
  value,
  share,
  color = "var(--brand)",
  note,
  suffix,
}: {
  label: string;
  value: number;
  /** 0–1, drives the bar width. */
  share: number;
  color?: string;
  note?: string;
  /** Satuan yang menempel di belakang angka, mis. "%". */
  suffix?: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-[16px] border border-[var(--line)] bg-[var(--card)] px-[18px] pb-4 pt-[18px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-semibold text-[var(--muted)]">
          {label}
        </span>
        {note && (
          <span className="mono rounded-md bg-[var(--line-soft)] px-[7px] py-[3px] text-[10.5px] font-bold text-[var(--muted)]">
            {note}
          </span>
        )}
      </div>
      <div className="text-[31px] font-extrabold leading-none tracking-[-0.04em]">
        {value.toLocaleString("en-GB")}
        {suffix && <span className="text-[18px]">{suffix}</span>}
      </div>
      <div className="h-[5px] overflow-hidden rounded-[4px] bg-[var(--line-soft)]">
        <div
          className="h-full rounded-[4px]"
          style={{
            width: `${Math.max(6, Math.min(100, share * 100))}%`,
            background: color,
          }}
        />
      </div>
    </div>
  );
}
