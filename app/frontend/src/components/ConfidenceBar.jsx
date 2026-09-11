export default function ConfidenceBar({ value }) {
  const pct = Math.round((value ?? 0) * 100);
  const tone = pct >= 75 ? "bg-brand-600" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] font-medium text-muted">
        <span>Confidence</span>
        <span className="text-ink">{pct}%</span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-line">
        <div className={`h-full ${tone} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
