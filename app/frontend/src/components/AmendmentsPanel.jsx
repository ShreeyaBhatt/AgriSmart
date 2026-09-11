import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import { useT } from "../i18n/useT.js";

const SEVERITY = {
  ok: { bar: "bg-brand-500", chip: "bg-brand-50 text-brand-700 ring-brand-200", icon: "check" },
  info: { bar: "bg-stone-300", chip: "bg-stone-100 text-stone-600 ring-stone-200", icon: "spark" },
  low: { bar: "bg-amber-500", chip: "bg-amber-50 text-amber-700 ring-amber-200", icon: "alert" },
  high: { bar: "bg-rose-500", chip: "bg-rose-50 text-rose-700 ring-rose-200", icon: "alert" },
};

const CATEGORY_ICON = {
  ph: "flask",
  organic_matter: "leaf",
  cec: "layers",
  nitrogen: "grain",
  phosphorus: "grain",
  potassium: "grain",
  texture: "scale",
};

export default function AmendmentsPanel({ report }) {
  const t = useT();
  if (!report) return null;

  return (
    <Card className="animate-fade-up p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon name="flask" className="h-4 w-4 text-brand-600" />
        {t("amendments.title")}
      </h2>

      <ul className="mt-3 space-y-2.5">
        {report.amendments.map((a, i) => {
          const s = SEVERITY[a.severity] || SEVERITY.info;
          return (
            <li key={i} className="flex gap-3 overflow-hidden rounded-xl border border-line bg-canvas/40">
              <span className={clsx("w-1 shrink-0", s.bar)} />
              <div className="min-w-0 py-2.5 pr-3">
                <div className="flex items-center gap-2">
                  <Icon name={CATEGORY_ICON[a.category] || "spark"} className="h-3.5 w-3.5 text-muted" />
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {CATEGORY_ICON[a.category] ? t(`amendments.category.${a.category}`) : a.category.replace(/_/g, " ")}
                  </span>
                  <span className={clsx("ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1", s.chip)}>
                    {SEVERITY[a.severity] ? t(`amendments.severity.${a.severity}`) : a.severity}
                  </span>
                </div>
                <p className="mt-1 text-sm text-ink/90">{a.finding}</p>
                <p className="mt-1 text-sm font-medium text-brand-800">→ {a.action}</p>
              </div>
            </li>
          );
        })}
      </ul>

      {report.data_gaps?.length > 0 && (
        <div className="mt-3 rounded-xl border border-dashed border-line p-3">
          <div className="text-[11px] font-medium uppercase tracking-wide text-faint">{t("amendments.dataGaps")}</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted">
            {report.data_gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}

      {report.citation && (
        <p className="mt-3 text-[11px] leading-relaxed text-faint">{report.citation}</p>
      )}
    </Card>
  );
}
