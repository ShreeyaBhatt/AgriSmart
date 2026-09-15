import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import SoilProfileCard from "../components/SoilProfileCard.jsx";
import AmendmentsPanel from "../components/AmendmentsPanel.jsx";
import CropsPanel from "../components/CropsPanel.jsx";
import Timeline from "../components/Timeline.jsx";
import LogForms from "../components/LogForms.jsx";
import AgentAdvisorCard from "../components/AgentAdvisorCard.jsx";
import { ProfileSkeleton } from "../components/Skeleton.jsx";
import { api } from "../api.js";
import { useLang, useT } from "../i18n/useT.js";
import { useLandUnit } from "../units/useLandUnit.js";
import { LAND_UNITS, formatArea } from "../units/convert.js";
import { usePlotSoil } from "../lib/PlotSoilContext.jsx";

export default function PlotDetail() {
  const { id } = useParams();
  const t = useT();
  const { lang } = useLang();
  const { unit, bighaRegion } = useLandUnit();
  const unitLabel = t(LAND_UNITS.find((u) => u.code === unit)?.key ?? "unit.ha");
  const navigate = useNavigate();
  const { pendingPlot, soilStatus } = usePlotSoil();
  const [plot, setPlot] = useState(null);
  const [amendments, setAmendments] = useState(null);
  const [crops, setCrops] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState("");

  const loadTimeline = useCallback(() => {
    api.timeline(id, lang).then(setTimeline).catch(() => {});
  }, [id, lang]);

  useEffect(() => {
    let alive = true;
    api.getPlot(id).then((p) => {
      if (!alive) return;
      setPlot(p);
      api.amendments(p.lat, p.lon).then(setAmendments).catch(() => {});
      api.crops(p.lat, p.lon).then(setCrops).catch(() => {});
    }).catch((e) => setError(e.detail || e.message));
    return () => { alive = false; };
  }, [id]);

  // Timeline titles are localized server-side, so re-fetch it whenever the
  // farmer switches language (loadTimeline already changes identity with lang).
  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

  // When the global soil poll finishes for THIS plot, re-fetch so the soil
  // profile card appears without requiring a manual "Refresh soil" press.
  useEffect(() => {
    if (pendingPlot?.id !== id || soilStatus !== "ready") return;
    api.getPlot(id).then(setPlot).catch(() => {});
  }, [pendingPlot, soilStatus, id]);

  const remove = async () => {
    if (!confirm(t("plot.confirmDelete"))) return;
    await api.deletePlot(id);
    navigate("/");
  };

  const refreshSoil = async () => {
    setPlot(await api.refreshSoil(id));
  };

  if (error) return <p className="text-sm text-rose-600">{error}</p>;
  if (!plot) return <ProfileSkeleton />;

  const area = formatArea(plot.area_ha, unit, bighaRegion);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <Link to="/" className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
            <Icon name="arrowLeft" className="h-3.5 w-3.5" /> {t("dashboard.title")}
          </Link>
          <h1 className="text-lg font-bold tracking-tight text-ink">{plot.name}</h1>
          <p className="text-xs text-muted">
            {plot.lat.toFixed(4)}, {plot.lon.toFixed(4)}
            {area != null && ` · ${area} ${unitLabel}`}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={refreshSoil}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas">
            <Icon name="refresh" className="h-3.5 w-3.5" /> {t("plot.refreshSoil")}
          </button>
          <button onClick={remove}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50">
            {t("action.delete")}
          </button>
        </div>
      </div>

      {/* Soil loading banner — shown while background fetch is running for this plot */}
      {pendingPlot?.id === id && soilStatus === "pending" && (
        <div className="flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50/70 px-4 py-3 dark:border-brand-800 dark:bg-brand-900/20">
          <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
          <div>
            <p className="text-sm font-medium text-brand-700 dark:text-brand-300">
              {t("plotNew.soilFetchingBg")}
            </p>
            <p className="text-[11px] text-brand-500 dark:text-brand-400">
              {t("plotNew.autoSoilHint")}
            </p>
          </div>
        </div>
      )}

      {/* Module G: Autonomous Agentic Advisor */}
      <AgentAdvisorCard plotId={id} lang={lang} />

      {plot.soil_snapshot && <SoilProfileCard profile={plot.soil_snapshot} />}

      <div className="grid gap-4 lg:grid-cols-2">
        {amendments && <AmendmentsPanel report={amendments} />}
        {crops && <CropsPanel rec={crops} />}
      </div>

      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Icon name="scale" className="h-4 w-4 text-brand-600" /> {t("plot.timeline")}
          </h2>
        </div>
        <LogForms plotId={id} onLogged={loadTimeline} />
        <div className="mt-4">
          <Timeline entries={timeline?.entries} />
        </div>
      </Card>
    </div>
  );
}
