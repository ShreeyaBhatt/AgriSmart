// Stacked sand / silt / clay bar in soil-ish tones. Values are % (may not sum to 100).
export default function FractionBar({ sand, silt, clay }) {
  const parts = [
    { key: "Sand", val: sand ?? 0, bar: "bg-earth-400", dot: "bg-earth-400" },
    { key: "Silt", val: silt ?? 0, bar: "bg-brand-300", dot: "bg-brand-300" },
    { key: "Clay", val: clay ?? 0, bar: "bg-earth-600", dot: "bg-earth-600" },
  ];
  const total = parts.reduce((s, p) => s + p.val, 0) || 1;

  return (
    <div>
      <div className="flex h-9 w-full overflow-hidden rounded-lg ring-1 ring-line">
        {parts.map((p) => {
          const w = (p.val / total) * 100;
          return (
            <div
              key={p.key}
              className={`${p.bar} flex items-center justify-center text-[11px] font-semibold text-white`}
              style={{ width: `${w}%` }}
              title={`${p.key} ${p.val}%`}
            >
              {w > 14 ? `${Math.round(p.val)}%` : ""}
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
        {parts.map((p) => (
          <span key={p.key} className="flex items-center gap-1.5">
            <span className={`inline-block h-2.5 w-2.5 rounded-sm ${p.dot}`} />
            {p.key}
            <span className="font-semibold text-ink">{p.val ?? "—"}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}
