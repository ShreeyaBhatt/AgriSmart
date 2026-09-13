import { useState, useEffect } from "react";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import { useT } from "../i18n/useT.js";
import clsx from "clsx";

const FACTS = [
  "soil.fact1",
  "soil.fact2",
  "soil.fact3",
  "soil.fact4",
  "soil.fact5",
];

export default function SoilLoadingExperience() {
  const t = useT();
  const [factIndex, setFactIndex] = useState(0);

  // Rotate facts every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setFactIndex((prev) => (prev + 1) % FACTS.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4 animate-fade-up">
      {/* Top Message Box */}
      <div className="flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800 dark:border-brand-800 dark:bg-brand-900/30 dark:text-brand-300">
        <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
        <span className="font-medium">
          {t("soil.loadingWhileWaiting")}
        </span>
      </div>

      {/* Fun Facts Carousel */}
      <Card className="overflow-hidden border-brand-200 bg-brand-50/50 dark:border-brand-800 dark:bg-brand-900/10">
        <div className="flex items-center gap-3 border-b border-brand-200/50 px-4 py-3 dark:border-brand-800/50">
          <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-brand-700 dark:bg-brand-800 dark:text-brand-300">
            <Icon name="sparkles" className="h-4 w-4" />
            <span className="absolute right-0 top-0 h-2 w-2 animate-ping rounded-full bg-brand-500" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-brand-900 dark:text-brand-100">
              {t("soil.loadingDidYouKnow")}
            </h3>
            <p className="text-xs font-medium text-brand-700 dark:text-brand-400">
              {t("soil.loadingAnalyzing")}
            </p>
          </div>
        </div>
        <div className="relative min-h-[80px] p-4">
          {FACTS.map((fact, idx) => (
            <p
              key={idx}
              className={clsx(
                "absolute inset-x-4 top-4 text-sm leading-relaxed text-ink transition-all duration-500",
                idx === factIndex
                  ? "translate-y-0 opacity-100"
                  : "translate-y-4 opacity-0 pointer-events-none"
              )}
            >
              {t(fact)}
            </p>
          ))}
        </div>
      </Card>

      {/* Sustainable Farming Tips */}
      <Card className="p-4">
        <h4 className="flex items-center gap-2 text-sm font-bold text-ink">
          <Icon name="leaf" className="h-4 w-4 text-emerald-500" />
          {t("soil.tipsTitle")}
        </h4>
        <div className="mt-4 space-y-3">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              <Icon name="droplet" className="h-3 w-3" />
            </div>
            <div>
              <p className="text-xs font-bold text-ink">{t("soil.tip1Title")}</p>
              <p className="text-[11px] text-muted">{t("soil.tip1Desc")}</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
              <Icon name="sun" className="h-3 w-3" />
            </div>
            <div>
              <p className="text-xs font-bold text-ink">{t("soil.tip2Title")}</p>
              <p className="text-[11px] text-muted">{t("soil.tip2Desc")}</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400">
              <Icon name="layers" className="h-3 w-3" />
            </div>
            <div>
              <p className="text-xs font-bold text-ink">{t("soil.tip3Title")}</p>
              <p className="text-[11px] text-muted">{t("soil.tip3Desc")}</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
