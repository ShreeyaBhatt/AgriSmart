import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import { useT } from "../i18n/useT.js";

function ScoreRing({ score }) {
  const pct = Math.round((score ?? 0) * 100);
  const tone = pct >= 70 ? "text-brand-600" : pct >= 40 ? "text-amber-500" : "text-faint";
  return (
    <div className="relative h-11 w-11 shrink-0">
      <svg viewBox="0 0 36 36" className="h-11 w-11 -rotate-90">
        <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="3" className="text-line" />
        <circle
          cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"
          className={tone}
          strokeDasharray={`${(pct / 100) * 97.4} 97.4`}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-ink">
        {pct}
      </span>
    </div>
  );
}

const SEASON_KEY = { kharif: "common.seasonKharif", rabi: "common.seasonRabi", zaid: "common.seasonZaid" };

export default function CropsPanel({ rec }) {
  const t = useT();
  if (!rec) return null;

  return (
    <Card className="animate-fade-up p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon name="sprout" className="h-4 w-4 text-brand-600" />
        {t("crops.title")}
        {rec.season && (
          <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium capitalize text-brand-700 ring-1 ring-brand-200">
            {SEASON_KEY[rec.season] ? t(SEASON_KEY[rec.season]) : rec.season}
          </span>
        )}
      </h2>

      <ol className="mt-3 space-y-2">
        {rec.ranked.slice(0, 6).map((c, i) => (
          <li
            key={c.crop}
            className={clsx(
              "flex items-center gap-3 rounded-xl border p-3",
              i === 0 ? "border-brand-200 bg-brand-50/60" : "border-line bg-canvas/40"
            )}
          >
            <ScoreRing score={c.score} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-semibold text-ink">{c.crop}</span>
                {i === 0 && (
                  <span className="rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    {t("crops.bestMatch")}
                  </span>
                )}
              </div>
              {c.reasons?.length > 0 && (
                <p className="mt-0.5 line-clamp-2 text-xs text-muted">{c.reasons.join(" · ")}</p>
              )}
              {c.caveats?.length > 0 && (
                <p className="mt-0.5 line-clamp-1 text-[11px] text-faint">{c.caveats[0]}</p>
              )}
            </div>
          </li>
        ))}
      </ol>

      <p className="mt-3 text-[11px] leading-relaxed text-faint">{rec.note}</p>
    </Card>
  );
}
