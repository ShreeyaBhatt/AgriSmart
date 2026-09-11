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
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-lg font-bold tracking-tight text-ink">{t("sustainability.title")}</h1>
        <p className="text-sm text-muted">
          A reproducible 0–100 score from water efficiency, chemical use and crop health.
        </p>
      </div>

      <Card className="grid gap-3 p-4 sm:grid-cols-2">
        <label className="text-[11px] font-medium text-faint">Irrigation applied this season (mm)
          <input className={INPUT + " mt-1"} inputMode="decimal" value={f.water_used_mm} onChange={set("water_used_mm")} />
        </label>
        <label className="text-[11px] font-medium text-faint">Crop water requirement (mm)
          <input className={INPUT + " mt-1"} inputMode="decimal" value={f.water_recommended_mm} onChange={set("water_recommended_mm")} />
        </label>
        <label className="text-[11px] font-medium text-faint">Agro-chemicals used (kg/ha)
          <input className={INPUT + " mt-1"} inputMode="decimal" value={f.chemical_used_kg_ha} onChange={set("chemical_used_kg_ha")} />
        </label>
        <label className="text-[11px] font-medium text-faint">Recommended (kg/ha)
          <input className={INPUT + " mt-1"} inputMode="decimal" value={f.chemical_recommended_kg_ha} onChange={set("chemical_recommended_kg_ha")} />
        </label>
        <label className="text-[11px] font-medium text-faint sm:col-span-2">Latest diagnosis (leave blank if healthy)
          <input className={INPUT + " mt-1"} placeholder="e.g. Tomato___Late_blight" value={f.disease_class} onChange={set("disease_class")} />
        </label>
        {error && <p className="text-xs text-rose-600 sm:col-span-2">{error}</p>}
        <button onClick={run} disabled={busy}
          className="rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint sm:col-span-2">
          {busy ? "…" : "Calculate score"}
        </button>
      </Card>

      {result && (
        <Card className="animate-fade-up p-5">
          <div className="flex items-end gap-3">
            <span className={clsx("text-5xl font-bold tracking-tight", BAND[result.band])}>
              {result.score}
            </span>
            <span className={clsx("mb-1 text-sm font-semibold capitalize", BAND[result.band])}>{result.band}</span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">Water overuse</div>
              <div className="text-sm font-semibold text-ink">{result.water_overuse_pct}%</div>
            </div>
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">Chemical overuse</div>
              <div className="text-sm font-semibold text-ink">{result.chemical_overuse_pct}%</div>
            </div>
            <div className="rounded-lg bg-canvas/60 p-2">
              <div className="text-[10px] uppercase text-faint">Crop health</div>
              <div className="text-sm font-semibold text-ink">{result.crop_health_pct}%</div>
            </div>
          </div>
          <ul className="mt-3 space-y-1.5">
            {result.tips.map((tip, i) => (
              <li key={i} className="flex gap-2 text-sm text-ink/90">
                <Icon name="spark" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" /> {tip}
              </li>
            ))}
          </ul>
          <p className="mt-3 rounded-lg bg-canvas/60 p-2 font-mono text-[10px] text-faint">{result.formula}</p>
        </Card>
      )}
    </div>
  );
}
