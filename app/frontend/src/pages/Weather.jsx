import { useEffect, useState } from "react";
import clsx from "clsx";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import Stat from "../components/Stat.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";

const SEV = {
  act: { chip: "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-800", dot: "bg-rose-500" },
  watch: { chip: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800", dot: "bg-amber-500" },
  info: { chip: "bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-950 dark:text-brand-300 dark:ring-brand-800", dot: "bg-brand-500" },
  recommend: { chip: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800", dot: "bg-emerald-500" },
};

export default function Weather() {
  const t = useT();
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [coords, setCoords] = useState({ lat: "", lon: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [advice, setAdvice] = useState(null);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => {});
  }, []);

  const run = async () => {
    let lat = Number(coords.lat);
    let lon = Number(coords.lon);
    let lastDisease = null;
    if (plotId) {
      const p = plots.find((x) => x.id === plotId);
      lat = p.lat;
      lon = p.lon;
      const scans = await api.listDiagnoses(plotId).catch(() => []);
      lastDisease = scans.find((s) => !s.abstained)?.predicted_class || null;
    }
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      setError(t("weather.chooseError"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      setAdvice(await api.weatherAdvice({ lat, lon, last_disease: lastDisease }));
    } catch (e) {
      setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-lg font-bold tracking-tight text-ink">{t("weather.title")}</h1>

      <Card className="space-y-3 p-4">
        {plots.length > 0 && (
          <label className="block text-[11px] font-medium text-faint">
            {t("weather.plotLabel")}
            <select
              value={plotId}
              onChange={(e) => setPlotId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400"
            >
              <option value="">{t("weather.enterCoords")}</option>
              {plots.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
        )}
        {!plotId && (
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded-lg border border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400"
              placeholder={t("common.latitude")} inputMode="decimal"
              value={coords.lat} onChange={(e) => setCoords({ ...coords, lat: e.target.value })} />
            <input className="rounded-lg border border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400"
              placeholder={t("common.longitude")} inputMode="decimal"
              value={coords.lon} onChange={(e) => setCoords({ ...coords, lon: e.target.value })} />
          </div>
        )}
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <button onClick={run} disabled={busy}
          className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint">
          {busy ? t("weather.checking") : t("action.analyse")}
        </button>
      </Card>

      {advice && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label={t("weather.rain24h")} value={advice.summary.rain_prob_24h_pct} unit="%" />
            <Stat label={t("weather.rainSum24h")} value={advice.summary.rain_sum_24h_mm} unit="mm" />
            <Stat label={t("weather.maxTemp")} value={advice.summary.temp_max_c} unit="°C" />
            <Stat label={t("weather.humidity")} value={advice.summary.humidity_mean_24h_pct} unit="%" />
          </div>
          <div className="space-y-2">
            {advice.actions.map((a, i) => {
              const s = SEV[a.severity] || SEV.info;
              return (
                <Card key={i} className="animate-fade-up p-4">
                  <div className="flex items-center gap-2">
                    <span className={clsx("h-2 w-2 rounded-full", s.dot)} />
                    <span className="text-sm font-semibold text-ink">{a.headline}</span>
                    <span className={clsx("ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1", s.chip)}>
                      {SEV[a.severity] ? t(`weather.severity.${a.severity}`) : a.severity}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm text-muted">{a.detail}</p>
                </Card>
              );
            })}
          </div>
          <p className="text-center text-[11px] text-faint">{t("weather.source")}</p>
        </>
      )}
    </div>
  );
}
