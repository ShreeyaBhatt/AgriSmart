import { useState } from "react";
import clsx from "clsx";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";

const INPUT =
  "w-full rounded-lg border border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400";
const BAND = {
  excellent: "text-brand-700",
  good: "text-brand-600",
  fair: "text-amber-600",
  poor: "text-rose-600",
};
const BAND_KEY = {
  excellent: "sustainability.band.excellent",
  good: "sustainability.band.good",
  fair: "sustainability.band.fair",
  poor: "sustainability.band.poor",
};

// A deliberately separate visual language from BAND/BAND_KEY above — see
// docs/sustainability.md: moisture_stress_risk is never derived from (and
// must never look like it's derived from) score/band, so an "Excellent"
// score and a "Severe" risk badge have to be able to sit side by side
// without either one reading as a mistake.
const RISK = {
  none: { text: "text-brand-700", dot: "bg-brand-500" },
  moderate: { text: "text-amber-700", dot: "bg-amber-500" },
  severe: { text: "text-rose-700", dot: "bg-rose-500" },
};
const RISK_KEY = {
  none: "sustainability.risk.none",
  moderate: "sustainability.risk.moderate",
  severe: "sustainability.risk.severe",
};

export default function Sustainability() {
  const t = useT();
  const [f, setF] = useState({
    water_used_mm: "320",
    water_recommended_mm: "300",
    chemical_used_kg_ha: "60",
    chemical_recommended_kg_ha: "50",
    disease_class: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      setResult(
        await api.sustainability({
          water_used_mm: Number(f.water_used_mm),
          water_recommended_mm: Number(f.water_recommended_mm),
          chemical_used_kg_ha: Number(f.chemical_used_kg_ha),
          chemical_recommended_kg_ha: Number(f.chemical_recommended_kg_ha),
          disease_class: f.disease_class || null,
        })
      );
    } catch (e) {
      setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-bold tracking-tight text-ink">{t("sustainability.title")}</h1>
        <p className="text-sm text-muted">{t("sustainability.pageHint")}</p>
      </div>

      {/* Same left-form / right-results split as Soil check / Weather, so a
          wide window isn't wasted on a narrow centered form. */}
      <div className="grid items-start gap-5 md:grid-cols-[minmax(0,380px)_1fr]">
        <Card className="grid gap-3 p-4 sm:grid-cols-2 md:sticky md:top-20 md:grid-cols-1">
          <label className="text-[11px] font-medium text-faint">{t("sustainability.waterUsed")}
            <input className={INPUT + " mt-1"} inputMode="decimal" value={f.water_used_mm} onChange={set("water_used_mm")} />
          </label>
          <label className="text-[11px] font-medium text-faint">{t("sustainability.waterRecommended")}
            <input className={INPUT + " mt-1"} inputMode="decimal" value={f.water_recommended_mm} onChange={set("water_recommended_mm")} />
          </label>
          <label className="text-[11px] font-medium text-faint">{t("sustainability.chemUsed")}
            <input className={INPUT + " mt-1"} inputMode="decimal" value={f.chemical_used_kg_ha} onChange={set("chemical_used_kg_ha")} />
          </label>
          <label className="text-[11px] font-medium text-faint">{t("sustainability.chemRecommended")}
            <input className={INPUT + " mt-1"} inputMode="decimal" value={f.chemical_recommended_kg_ha} onChange={set("chemical_recommended_kg_ha")} />
          </label>
          <label className="text-[11px] font-medium text-faint sm:col-span-2 md:col-span-1">{t("sustainability.diseaseLabel")}
            <input className={INPUT + " mt-1"} placeholder={t("sustainability.diseasePlaceholder")} value={f.disease_class} onChange={set("disease_class")} />
          </label>
          {error && <p className="text-xs text-rose-600 sm:col-span-2 md:col-span-1">{error}</p>}
          <button onClick={run} disabled={busy}
            className="rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint sm:col-span-2 md:col-span-1">
            {busy ? "…" : t("sustainability.calculate")}
          </button>
        </Card>

        <div className="min-w-0">
        {result && (
        <Card className="animate-fade-up p-5">
          <div className="flex items-end gap-3">
            <span className={clsx("text-5xl font-bold tracking-tight", BAND[result.band])}>
              {result.score}
            </span>
            <span className={clsx("mb-1 text-sm font-semibold capitalize", BAND[result.band])}>
              {BAND_KEY[result.band] ? t(BAND_KEY[result.band]) : result.band}
            </span>
          </div>
          {/* Always shown, not just when a risk is present — the score/band
              answers "how efficient is this farm", not "is anything wrong
              right now"; that's what the risk indicator below is for. */}
          <p className="mt-1 text-xs text-faint">{t("sustainability.scoreDisclaimer")}</p>

          {result.moisture_stress_risk !== "none" && (
            <div className={clsx(
              "mt-3 flex items-start gap-2 rounded-lg p-3 text-xs ring-1",
              result.moisture_stress_risk === "severe"
                ? "bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:ring-rose-800"
                : "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-800"
            )}>
              <Icon name="alert" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                {t(result.moisture_stress_risk === "severe"
                  ? "sustainability.severeRiskBanner"
                  : "sustainability.moderateRiskBanner")}
                {" "}({t("sustainability.waterDeviation")}: {result.water_deviation_pct > 0 ? "+" : ""}
                {result.water_deviation_pct}%)
              </span>
            </div>
          )}

          <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">{t("sustainability.waterDeviation")}</div>
              <div className={clsx("text-sm font-semibold", result.moisture_stress_risk !== "none" ? "text-rose-600" : "text-ink")}>
                {result.water_deviation_pct > 0 ? "+" : ""}{result.water_deviation_pct}%
              </div>
            </div>
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">{t("sustainability.moistureStressRisk")}</div>
              <div className="mt-0.5 flex items-center justify-center gap-1">
                <span className={clsx("h-1.5 w-1.5 rounded-full", RISK[result.moisture_stress_risk].dot)} />
                <span className={clsx("text-sm font-semibold capitalize", RISK[result.moisture_stress_risk].text)}>
                  {t(RISK_KEY[result.moisture_stress_risk])}
                </span>
              </div>
            </div>
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">{t("sustainability.chemicalOveruse")}</div>
              <div className="text-sm font-semibold text-ink">{result.chemical_overuse_pct}%</div>
            </div>
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">{t("sustainability.cropHealth")}</div>
              <div className="text-sm font-semibold text-ink">{result.crop_health_pct}%</div>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-center">
            <div className="rounded-lg bg-canvas/40 p-2">
              <div className="text-[10px] uppercase text-faint">{t("sustainability.waterOveruse")}</div>
              <div className="text-sm font-semibold text-ink">{result.water_overuse_pct}%</div>
            </div>
            <div className="rounded-lg bg-canvas/40 p-2">
              <div className="text-[10px] uppercase text-faint">{t("sustainability.waterDeficit")}</div>
              <div className="text-sm font-semibold text-ink">{result.water_deficit_pct}%</div>
            </div>
          </div>
          {result.ai_notes && (
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-800">
              <Icon name="alert" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{result.ai_notes}</span>
            </div>
          )}
          <ul className="mt-3 space-y-1.5">
            {result.tips.map((tip, i) => (
              <li key={i} className="flex gap-2 text-sm text-muted">
                <Icon name="spark" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" /> {tip}
              </li>
            ))}
          </ul>
          <p className="mt-3 rounded-lg bg-canvas/60 p-2 font-mono text-[10px] text-faint">{result.formula}</p>
        </Card>
        )}
        </div>
      </div>
    </div>
  );
}
