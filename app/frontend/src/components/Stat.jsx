import clsx from "clsx";
import { toneClasses } from "../lib/ratings.js";

export default function Stat({ label, value, unit, hint, rating }) {
  const empty = value === null || value === undefined || value === "";
  const tone = rating ? toneClasses[rating.tone] : null;

  return (
    <div className="rounded-xl border border-line bg-canvas/60 px-3 py-2.5">
      <div className="flex items-center justify-between gap-1">
        <span className="truncate text-[11px] font-medium uppercase leading-tight tracking-wide text-faint">
          {label}
        </span>
        {rating && !empty && (
          <span className={clsx("rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1", tone.chip)}>
            {rating.label}
          </span>
        )}
      </div>
      <div className="mt-1 text-lg font-semibold text-ink">
        {empty ? <span className="text-faint">—</span> : value}
        {!empty && unit && <span className="ml-1 text-xs font-normal text-muted">{unit}</span>}
      </div>
      {hint && <div className="text-[11px] text-faint">{hint}</div>}
    </div>
  );
}
