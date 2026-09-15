import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
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
  const [refreshingSoil, setRefreshingSoil] = useState(false);
  const [refreshSuccess, setRefreshSuccess] = useState(false);
  const [refreshError, setRefreshError] = useState("");

  const loadTimeline = useCallback(() => {
    api.timeline(id, lang).then(setTimeline).catch(() => {});
  }, [id, lang]);

  useEffect(() => {
    let alive = true;
    api.getPlot(id).then((p) => {
      if (!alive) return;
      setPlot(p);
      // The amendments/crops text is localized server-side at request time
      // (like /predict), so it doesn't move with the UI when the farmer
      // switches language afterwards — this effect re-runs on `lang` too.
      api.amendments(p.lat, p.lon, undefined, lang).then(setAmendments).catch(() => {});
      api.crops(p.lat, p.lon, undefined, undefined, lang).then(setCrops).catch(() => {});
    }).catch((e) => setError(e.detail || e.message));
    return () => { alive = false; };
  }, [id, lang]);

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
    setRefreshingSoil(true);
    setRefreshError("");
    setRefreshSuccess(false);
    try {
      const updatedPlot = await api.refreshSoil(id);
      setPlot(updatedPlot);
      setRefreshSuccess(true);
      setTimeout(() => setRefreshSuccess(false), 3000);
      if (updatedPlot) {
        api.amendments(updatedPlot.lat, updatedPlot.lon, undefined, lang).then(setAmendments).catch(() => {});
        api.crops(updatedPlot.lat, updatedPlot.lon, undefined, undefined, lang).then(setCrops).catch(() => {});
      }
      loadTimeline();
    } catch (err) {
      setRefreshError(err.detail || err.message || t("plot.refreshError"));
    } finally {
      setRefreshingSoil(false);
    }
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
        <div className="flex flex-wrap items-center gap-2">
          {refreshSuccess && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 dark:text-brand-400 animate-fade-up">
              <Icon name="check" className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
              {t("plot.soilRefreshed")}
            </span>
          )}
          <button
            onClick={refreshSoil}
            disabled={refreshingSoil}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas transition disabled:cursor-not-allowed disabled:opacity-60"
            title={t("plot.refreshSoil")}
          >
            <Icon
              name="refresh"
              className={clsx("h-3.5 w-3.5", refreshingSoil && "animate-spin text-brand-600")}
            />
            {refreshingSoil ? t("plot.refreshingSoil") : t("plot.refreshSoil")}
          </button>
          <button
            onClick={remove}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50"
          >
            <Icon name="trash" className="h-3.5 w-3.5" /> {t("action.delete")}
          </button>
        </div>
      </div>

      {refreshError && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700 animate-fade-up">
          <div className="flex items-center gap-2">
            <Icon name="alert" className="h-4 w-4 shrink-0" />
            <span>{refreshError}</span>
          </div>
          <button
            onClick={() => setRefreshError("")}
            className="text-rose-500 hover:text-rose-700"
          >
            <Icon name="close" className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

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
