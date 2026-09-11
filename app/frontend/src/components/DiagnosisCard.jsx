import { Link } from "react-router-dom";
import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import ConfidenceBar from "./ConfidenceBar.jsx";
import { mediaUrl } from "../api.js";
import { isAbstain, isHealthy, prettyLabel } from "../lib/labels.js";
import { useT } from "../i18n/useT.js";

export default function DiagnosisCard({ diagnosis, originalUrl }) {
  const t = useT();
  const abstain = diagnosis.abstained || isAbstain(diagnosis.predicted_class);
  const healthy = !abstain && isHealthy(diagnosis.predicted_class);

  const tone = abstain
    ? { chip: "bg-amber-50 text-amber-700 ring-amber-200", label: t("scan.unclear") }
    : healthy
      ? { chip: "bg-brand-50 text-brand-700 ring-brand-200", label: t("scan.healthy") }
      : { chip: "bg-rose-50 text-rose-700 ring-rose-200", label: prettyLabel(diagnosis.predicted_class) };

  const img = originalUrl || mediaUrl(diagnosis.image_url);
  const cam = mediaUrl(diagnosis.gradcam_url);

  return (
    <Card className="animate-fade-up overflow-hidden">
      <div className="border-b border-line bg-gradient-to-b from-canvas/70 to-transparent px-5 pt-4 pb-4">
        <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-muted">
          <Icon name="camera" className="h-4 w-4" /> {t("scan.title")}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight text-ink">{tone.label}</h2>
          <span className={clsx("rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1", tone.chip)}>
            {abstain ? "abstained" : healthy ? "healthy" : "disease"}
          </span>
        </div>
        {!abstain && (
          <div className="mt-2 max-w-xs">
            <ConfidenceBar value={diagnosis.confidence} />
          </div>
        )}
      </div>

      <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">
        {(img || cam) && (
          <div className="grid grid-cols-2 gap-2">
            {img && (
              <figure>
                <img src={img} alt="leaf" className="aspect-square w-full rounded-lg object-cover ring-1 ring-line" />
                <figcaption className="mt-1 text-center text-[10px] text-faint">Your photo</figcaption>
              </figure>
            )}
            {cam && (
              <figure>
                <img src={cam} alt="Grad-CAM" className="aspect-square w-full rounded-lg object-cover ring-1 ring-line" />
                <figcaption className="mt-1 text-center text-[10px] text-faint">Affected area</figcaption>
              </figure>
            )}
          </div>
        )}

        <div>
          <div className="text-[11px] font-medium uppercase tracking-wide text-faint">
            {t("scan.precautions")}
          </div>
          <ul className="mt-1.5 space-y-1.5">
            {(diagnosis.precautions || []).map((p, i) => (
              <li key={i} className="flex gap-2 text-sm text-ink/90">
                <Icon name="check" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" />
                {p}
              </li>
            ))}
          </ul>
          {!abstain && (
            <Link
              to="/assistant"
              state={{ prefill: `Tell me more about ${prettyLabel(diagnosis.predicted_class)} and how to treat it.` }}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50"
            >
              <Icon name="chat" className="h-3.5 w-3.5" />
              Ask the assistant
            </Link>
          )}
        </div>
      </div>

      {diagnosis.model_version && (
        <p className="px-5 pb-3 text-[10px] text-faint">model {diagnosis.model_version}</p>
      )}
    </Card>
  );
}
