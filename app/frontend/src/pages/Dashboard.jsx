import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import EmptyState from "../components/EmptyState.jsx";
import PlotCard from "../components/PlotCard.jsx";
import PlotsMap from "../components/PlotsMap.jsx";
import Stat from "../components/Stat.jsx";
import { api, mediaUrl } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { prettyLabel, isAbstain } from "../lib/labels.js";
import { useLang, useT } from "../i18n/useT.js";

function greetingKey() {
  const h = new Date().getHours();
  if (h < 12) return "dashboard.greetingMorning";
  if (h < 18) return "dashboard.greetingAfternoon";
  return "dashboard.greetingEvening";
}

export default function Dashboard() {
  const t = useT();
  const { lang } = useLang();
  const { user } = useAuth();
  const [plots, setPlots] = useState(null);
  const [scans, setScans] = useState([]);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => setPlots([]));
    api.listDiagnoses(undefined, lang).then((d) => setScans(d.slice(0, 4))).catch(() => {});
  }, [lang]);

  return (
    <div className="space-y-5">
      <Card className="animate-fade-up border-brand-200 bg-brand-50/70 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-700 text-white">
              <Icon name="sprout" className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-ink">
                {t(greetingKey())}
                {user && !user.is_guest && user.name ? `, ${user.name.split(" ")[0]}` : ""}
              </h1>
              <p className="text-sm text-muted">{t("app.tagline")}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Link
              to="/scan"
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-700 px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-brand-800"
            >
              <Icon name="camera" className="h-4 w-4" /> {t("action.scanLeaf")}
            </Link>
            <Link
              to="/plots/new"
              className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3.5 py-2 text-sm font-medium text-muted hover:bg-canvas"
            >
              <Icon name="plus" className="h-4 w-4" /> {t("action.addPlot")}
            </Link>
          </div>
        </div>
      </Card>

      {user?.is_guest && (
        <div className="flex items-center gap-2.5 rounded-xl bg-earth-400/10 px-4 py-2.5 text-sm text-earth-600 ring-1 ring-earth-400/20">
          <Icon name="alert" className="h-4 w-4 shrink-0" />
          {t("dashboard.guestBanner")}
        </div>
      )}

      {plots !== null && plots.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <Stat label={t("nav.plots")} value={plots.length} />
          <Stat label={t("dashboard.recentScans")} value={scans.length} />
          <Stat label={t("login.cropLabel")} value={user?.primary_crop || "—"} />
        </div>
      )}

      {plots === null ? (
        <div className="h-64 animate-pulse rounded-2xl bg-line" />
      ) : plots.length === 0 ? (
        <EmptyState
          icon="map"
          title={t("dashboard.noPlots")}
          hint={user?.primary_crop ? t("dashboard.noPlotsHint") : undefined}
          action={
            <Link
              to="/plots/new"
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-700 px-4 py-2 text-sm font-semibold text-white"
            >
              <Icon name="plus" className="h-4 w-4" /> {t("action.addPlot")}
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <Card className="overflow-hidden">
            <PlotsMap plots={plots} height="20rem" />
          </Card>
          <div className="space-y-2">
            {plots.map((p) => (
              <PlotCard key={p.id} plot={p} />
            ))}
          </div>
        </div>
      )}

      {scans.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink">{t("dashboard.recentScans")}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {scans.map((s) => (
              <Card key={s.id} className="overflow-hidden">
                {s.image_url && (
                  <img src={mediaUrl(s.image_url)} alt="" className="aspect-video w-full object-cover" />
                )}
                <div className="p-3">
                  <div className="truncate text-xs font-semibold text-ink">
                    {s.abstained || isAbstain(s.predicted_class)
                      ? t("scan.unclear")
                      : s.predicted_label || prettyLabel(s.predicted_class)}
                  </div>
                  <div className="text-[11px] text-faint">
                    {new Date(s.created_at).toLocaleDateString()} · {Math.round(s.confidence * 100)}%
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
