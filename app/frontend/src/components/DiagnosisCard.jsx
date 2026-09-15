import { Link } from "react-router-dom";
import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import ConfidenceBar from "./ConfidenceBar.jsx";
import { mediaUrl } from "../api.js";
import { isAbstain, isHealthy, prettyLabel } from "../lib/labels.js";
import { useT } from "../i18n/useT.js";

// Status derived only from fields the API actually returns (abstained /
// healthy) — no fabricated severity score. "critical" is defined for a
// future real per-class severity signal (e.g. from sustainability.py's
// _SEVERITY table, not currently exposed on DiagnosisOut) but is not
// selected today: it used to be picked by `confidence >= 0.5`, which
// backwards from ConfidenceBar's own coloring just below it (there, LOW
// confidence is the rose/concerning state — the model being unsure, not
// the disease being severe) — a confidently-identified mild issue got a
// scary red "CRITICAL" banner while an uncertain guess at a severe disease
// only got "WARNING", and the two widgets visually contradicted each
// other. Every real (non-healthy, non-abstained) detection is "warning"
// until a genuine severity signal is wired through.
const TIER = {
  healthy: {
    labelKey: "scan.tag.healthy",
    banner: "border-brand-300 bg-brand-50 text-brand-800",
    badge: "bg-brand-600 text-white",
    icon: "check",
  },
  warning: {
    labelKey: "scan.tag.warning",
    banner: "border-amber-300 bg-amber-50 text-amber-800",
    badge: "bg-amber-500 text-white",
    icon: "alert",
  },
  critical: {
    labelKey: "scan.tag.critical",
    banner: "border-rose-300 bg-rose-50 text-rose-800",
    badge: "bg-rose-600 text-white",
    icon: "alert",
  },
  abstained: {
    labelKey: "scan.tag.abstained",
    banner: "border-amber-300 bg-amber-50 text-amber-800",
    badge: "bg-amber-500 text-white",
    icon: "refresh",
  },
  not_a_leaf: {
    labelKey: "scan.tag.notALeaf",
    banner: "border-amber-300 bg-amber-50 text-amber-900",
    badge: "bg-amber-600 text-white",
    icon: "alert",
  },
  unsupported_crop: {
    labelKey: "scan.tag.unsupportedCrop",
    banner: "border-amber-300 bg-amber-50 text-amber-900",
    badge: "bg-amber-600 text-white",
    icon: "alert",
  },
};

export default function DiagnosisCard({ diagnosis, originalUrl }) {
  const t = useT();
  const isNotLeaf = diagnosis.rejection_reason === "not_a_leaf";
  const isUnsupportedCrop = diagnosis.rejection_reason === "unsupported_crop";
  const abstain = isNotLeaf || isUnsupportedCrop || diagnosis.abstained || isAbstain(diagnosis.predicted_class);
  const healthy = !abstain && isHealthy(diagnosis.predicted_class);

  const label = isNotLeaf
    ? t("scan.notALeaf")
    : isUnsupportedCrop
      ? t("scan.unsupportedCrop")
      : abstain
        ? t("scan.unclear")
        : healthy
          ? t("scan.healthy")
          : diagnosis.predicted_label || prettyLabel(diagnosis.predicted_class);

  const tierKey = isNotLeaf
    ? "not_a_leaf"
    : isUnsupportedCrop
      ? "unsupported_crop"
      : abstain
        ? "abstained"
        : healthy
          ? "healthy"
          : "warning";
  const tier = TIER[tierKey];

  const img = originalUrl || mediaUrl(diagnosis.image_url);
  const cam = (abstain || isNotLeaf || isUnsupportedCrop) ? null : mediaUrl(diagnosis.gradcam_url);

  return (
    <Card className="animate-fade-up overflow-hidden border-2">
      <div className="px-5 pt-4 pb-4">
        <div className={clsx("flex items-center gap-3 rounded-2xl border-2 px-4 py-3", tier.banner)}>
          <span className={clsx("flex h-10 w-10 shrink-0 items-center justify-center rounded-full", tier.badge)}>
            <Icon name={tier.icon} className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="text-[11px] font-bold uppercase tracking-wide">{t(tier.labelKey)}</div>
            <div className="truncate text-xl font-extrabold tracking-tight">{label}</div>
          </div>
        </div>

        {!abstain && (
          <div className="mt-3 max-w-xs">
            <ConfidenceBar value={diagnosis.confidence} />
          </div>
        )}

        {diagnosis.crop_warning && (
          <div className="mt-3 flex items-start gap-2.5 rounded-2xl border-2 border-rose-300 bg-rose-50 px-4 py-3 text-rose-800">
            <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0">
              <div className="text-[11px] font-bold uppercase tracking-wide">{t("scan.cropMismatchTitle")}</div>
              <p className="mt-0.5 text-sm leading-snug">{diagnosis.crop_warning}</p>
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">
        {(img || cam) && (
          <div className="grid grid-cols-2 gap-2 content-start">
            {cam && (
              <figure>
                <img src={cam} alt={t("scan.affectedArea")} className="aspect-square w-full rounded-lg object-cover ring-2 ring-line" />
                <figcaption className="mt-1 text-center text-[10px] font-medium text-muted">{t("scan.affectedArea")}</figcaption>
              </figure>
            )}
            {img && (
              <figure className={cam ? "" : "col-span-2"}>
                <img src={img} alt={t("scan.yourPhoto")} className="aspect-square w-full rounded-lg object-cover ring-2 ring-line" />
                <figcaption className="mt-1 text-center text-[10px] text-faint">{t("scan.yourPhoto")}</figcaption>
              </figure>
            )}
            {cam && (
              <div className="col-span-2 mt-1 flex items-center gap-2">
                <div className="h-1.5 flex-1 rounded-full bg-gradient-to-r from-transparent via-amber-400 to-rose-500" />
                <span className="text-[10px] font-medium text-faint">{t("scan.heatmapLegend")}</span>
              </div>
            )}
          </div>
        )}

        <div className="rounded-2xl border-2 border-line bg-canvas/40 p-3.5">
          <div className={clsx(
            "flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide",
            (isNotLeaf || isUnsupportedCrop) ? "text-amber-800" : "text-brand-700"
          )}>
            <Icon name={(isNotLeaf || isUnsupportedCrop) ? "alert" : "flask"} className="h-4 w-4" />
            {(isNotLeaf || isUnsupportedCrop) ? t("scan.safetyNotice") : t("scan.precautions")}
          </div>
          <ol className="mt-2.5 space-y-2.5">
            {(diagnosis.precautions || []).map((p, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className={clsx(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white",
                  (isNotLeaf || isUnsupportedCrop) ? "bg-amber-600" : "bg-brand-600"
                )}>
                  {i + 1}
                </span>
                <span className="pt-0.5 text-sm font-medium leading-snug text-ink">{p}</span>
              </li>
            ))}
          </ol>
          {!abstain && (
            <Link
              to="/assistant"
              state={{
                prefill: `${t("scan.assistantPrefillPrefix")} ${diagnosis.predicted_label || prettyLabel(diagnosis.predicted_class)} ${t("scan.assistantPrefillSuffix")}`,
              }}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border-2 border-line bg-surface px-3 py-1.5 text-xs font-semibold text-brand-700 transition hover:border-brand-400 hover:bg-brand-50"
            >
              <Icon name="chat" className="h-3.5 w-3.5" />
              {t("scan.askAssistant")}
            </Link>
          )}
          {(isNotLeaf || isUnsupportedCrop) && (
            <Link
              to="/assistant"
              state={{
                prefill: "Which crops and diseases does AgriSmart support?",
              }}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border-2 border-line bg-surface px-3 py-1.5 text-xs font-semibold text-amber-800 transition hover:border-amber-400 hover:bg-amber-50"
            >
              <Icon name="chat" className="h-3.5 w-3.5" />
              {t("scan.askAssistant")}
            </Link>
          )}
        </div>
      </div>

    </Card>
  );
}
