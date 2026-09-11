import { useT } from "../i18n/useT.js";

export default function ConfidenceBar({ value }) {
  const t = useT();
  const pct = Math.round((value ?? 0) * 100);
  const tone = pct >= 75 ? "bg-brand-600" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wide text-muted">
        <span>{t("scan.confidence")}</span>
        <span className="text-sm normal-case tracking-normal text-ink">{pct}%</span>
      </div>
      <div className="mt-1.5 h-3 w-full overflow-hidden rounded-full bg-line ring-2 ring-line">
        <div className={`h-full ${tone} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
