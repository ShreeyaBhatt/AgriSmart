import { rating, phFraction, toneClasses } from "../lib/ratings.js";
import { useT } from "../i18n/useT.js";

// pH shown on a 3.5–9.5 spectrum with a pointer at the measured value.
export default function PhScale({ ph, uncertainty }) {
  const t = useT();
  if (ph == null) {
    return <div className="text-sm text-faint">{t("soil.phUnavailable")}</div>;
  }
  const pct = phFraction(ph) * 100;
  const r = rating.ph(ph);
  const tone = toneClasses[r.tone];

  return (
    <div>
      <div className="flex items-end justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold tracking-tight text-ink">{ph.toFixed(1)}</span>
          <span className={"text-xs font-semibold " + tone.text}>{r.label}</span>
        </div>
        {uncertainty != null && (
          <span className="text-[11px] text-faint">±{uncertainty} (90% CI)</span>
        )}
      </div>

      <div className="relative mt-2 h-3 rounded-full bg-gradient-to-r from-rose-400 via-lime-400 to-violet-400">
        <div
          className="absolute -top-1 h-5 w-1.5 -translate-x-1/2 rounded-full bg-ink shadow ring-2 ring-white"
          style={{ left: `${pct}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] font-medium text-faint">
        <span>3.5</span>
        <span>{t("soil.acidic")}</span>
        <span>6.5–7.5</span>
        <span>{t("soil.alkaline")}</span>
        <span>9.5</span>
      </div>
    </div>
  );
}
