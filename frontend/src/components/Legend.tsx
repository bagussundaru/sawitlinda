import { LEGEND } from "@/lib/severity";

export default function Legend({ filled = false }: { filled?: boolean }) {
  return (
    <div className="mt-3 flex flex-wrap gap-4 text-[12.5px]">
      {LEGEND.map((item) => (
        <span
          key={item.label}
          className="flex items-center gap-[6px] text-[var(--muted)]"
        >
          <i
            className="h-3 w-3 rounded-[3px] border-2"
            style={{
              borderColor: item.color,
              background: filled ? item.color : "transparent",
            }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}
