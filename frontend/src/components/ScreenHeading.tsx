export default function ScreenHeading({
  title,
  subtitle,
  flag,
}: {
  title: string;
  subtitle?: string;
  flag?: string;
}) {
  return (
    <>
      <h2 className="mb-1 text-xl font-bold">
        {title}
        {flag && (
          <span className="ml-2 align-middle rounded-full bg-[var(--amber-bg)] px-2 py-[2px] text-[10.5px] font-bold text-[var(--amber)]">
            {flag}
          </span>
        )}
      </h2>
      {subtitle && (
        <p className="mb-5 text-sm text-[var(--muted)]">{subtitle}</p>
      )}
    </>
  );
}
