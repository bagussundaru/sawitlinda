export function Card({
  title,
  action,
  children,
  className = "",
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-[14px] border border-[var(--line)] bg-[var(--card)] p-[18px] shadow-[0_1px_2px_rgba(16,40,32,.04)] ${className}`}
    >
      {title && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-[14.5px] font-bold">{title}</h3>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatCard({
  value,
  label,
  tone = "default",
}: {
  value: number | string;
  label: string;
  tone?: "default" | "good" | "warn" | "bad";
}) {
  const color = {
    default: "var(--ink)",
    good: "var(--green)",
    warn: "var(--chart-3)",
    bad: "var(--chart-4)",
  }[tone];

  return (
    <div className="rounded-[14px] border border-[var(--line)] bg-[var(--card)] px-[18px] py-4 shadow-[0_1px_2px_rgba(16,40,32,.04)]">
      <div className="text-[12.5px] text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-[26px] font-bold leading-tight" style={{ color }}>
        {typeof value === "number" ? value.toLocaleString("id-ID") : value}
      </div>
    </div>
  );
}
