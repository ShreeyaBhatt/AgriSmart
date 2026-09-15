import { useState, useRef, useEffect } from "react";
import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import Stat from "./Stat.jsx";
import FractionBar from "./FractionBar.jsx";
import PhScale from "./PhScale.jsx";
import { rating } from "../lib/ratings.js";
import { useT } from "../i18n/useT.js";

function SourceBadge({ source, t }) {
  const offline = source?.includes("offline");
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1",
        offline ? "bg-amber-50 text-amber-700 ring-amber-200" : "bg-brand-50 text-brand-700 ring-brand-200"
      )}
      title={offline ? t("soil.offlineSource") : t("soil.liveSource")}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", offline ? "bg-amber-500" : "bg-brand-500")} />
      {source}
    </span>
  );
}

const TEXTURES = [
  { value: "sand", label: "Sand" },
  { value: "loamy sand", label: "Loamy sand" },
  { value: "sandy loam", label: "Sandy loam" },
  { value: "loam", label: "Loam" },
  { value: "silt loam", label: "Silt loam" },
  { value: "silt", label: "Silt" },
  { value: "sandy clay loam", label: "Sandy clay loam" },
  { value: "clay loam", label: "Clay loam" },
  { value: "silty clay loam", label: "Silty clay loam" },
  { value: "sandy clay", label: "Sandy clay" },
  { value: "silty clay", label: "Silty clay" },
  { value: "clay", label: "Clay" },
];

function TextureDropdown({ currentTexture, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    const onPointer = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  const choose = (val) => {
    onChange(val);
    setOpen(false);
  };

  const isOverridden = Boolean(currentTexture && TEXTURES.some(t => t.value === currentTexture));
  const currentLabel = TEXTURES.find(t => t.value === currentTexture)?.label || "Override...";

  return (
    <div ref={ref} className="relative z-50">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={[
          "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition",
          "border-line bg-surface text-ink shadow-sm",
          "hover:border-brand-400 hover:text-brand-700",
          open ? "border-brand-400 text-brand-700" : "",
        ].join(" ")}
      >
        <span>{currentLabel}</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={["h-3 w-3 shrink-0 text-faint transition-transform duration-200", open ? "rotate-180" : ""].join(" ")}><path d="m6 9 6 6 6-6" /></svg>
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1.5 w-52 rounded-xl border border-line bg-surface p-1.5 shadow-lg ring-1 ring-black/5 animate-fade-up max-h-64 overflow-y-auto custom-scrollbar">
          <div className="flex flex-col gap-0.5">
            <button
              type="button"
              onClick={() => choose(null)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs font-semibold text-brand-700 hover:bg-brand-50 dark:hover:bg-brand-900/30 border-b border-line mb-1 transition"
            >
              <span>Auto (GPS Detected)</span>
              <Icon name="refresh" className="h-3 w-3 text-brand-500" />
            </button>
            {TEXTURES.map((t) => {
              const active = t.value === currentTexture;
              return (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => choose(t.value)}
                  className={[
                    "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium transition",
                    active ? "bg-brand-600 text-white" : "text-ink hover:bg-canvas",
                  ].join(" ")}
                >
                  <span>{t.label}</span>
                  {active && <Icon name="check" className="h-3.5 w-3.5 shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SoilProfileCard({ profile: p, onTextureOverride }) {
  const t = useT();
  if (!p) return null;
  const u = p.uncertainty || {};
  const loc = [p.shc_district, p.shc_state].filter(Boolean).join(", ");
  const offline = p.source?.includes("offline");

  const handleTextureChange = (e) => {
    if (onTextureOverride) onTextureOverride(e.target.value);
  };

  return (
    <Card className="animate-fade-up overflow-clip">
      {offline && (
        <div className="flex items-center gap-2 bg-amber-50 px-5 py-2.5 text-xs font-semibold text-amber-800 border-b border-amber-200">
          <Icon name="alert" className="h-4 w-4 shrink-0" /> 
          {t("soil.offlineWarning")}
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line bg-gradient-to-b from-brand-50/60 to-transparent dark:from-brand-900/30 dark:to-transparent px-5 pt-4 pb-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-brand-700">
            <Icon name="layers" className="h-4 w-4" />
            {t("plot.soil")}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <h2 className="text-2xl font-bold capitalize tracking-tight text-ink">
              {p.texture_class || t("soil.unknownTexture")}
            </h2>
            {onTextureOverride && (
              <TextureDropdown currentTexture={p.texture_class} onChange={onTextureOverride} />
            )}
          </div>
          <p className="mt-0.5 text-xs text-muted">
            {p.wrb_class ? `${p.wrb_class} (WRB)` : t("soil.wrbNA")}
            {p.wrb_probability != null && (
              <span className="text-faint"> · p={p.wrb_probability}</span>
            )}
          </p>
        </div>
        <SourceBadge source={p.source} t={t} />
      </div>

      <div className="space-y-5 px-5 py-4">
        <div>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            {t("soil.particleSize")} · {p.depth_basis}
          </div>
          <FractionBar sand={p.sand_pct} silt={p.silt_pct} clay={p.clay_pct} />
        </div>

        <div className="rounded-xl border border-line bg-canvas/50 p-3.5">
          <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            <Icon name="flask" className="h-3.5 w-3.5" /> {t("soil.phReaction")}
          </div>
          <PhScale ph={p.ph} uncertainty={u.ph} />
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label={t("soil.stat.orgC")} value={p.organic_carbon_pct} unit="%" rating={rating.ocPct(p.organic_carbon_pct)}
            hint={p.organic_carbon_g_kg != null ? `${p.organic_carbon_g_kg} g/kg` : null} />
          <Stat label={t("soil.stat.totalN")} value={p.total_nitrogen_g_kg} unit="g/kg" />
          <Stat label={t("soil.stat.cec")} value={p.cec_cmol_kg} unit="cmol/kg" rating={rating.cec(p.cec_cmol_kg)} />
          <Stat label={t("soil.stat.bulkDensity")} value={p.bulk_density_kg_dm3} unit="kg/dm³" />
          <Stat label={t("soil.stat.coarseFrag")} value={p.coarse_fragments_pct} unit="%" />
          <Stat label={t("soil.stat.sand")} value={p.sand_pct} unit="%" />
          <Stat label={t("soil.stat.silt")} value={p.silt_pct} unit="%" />
          <Stat label={t("soil.stat.clay")} value={p.clay_pct} unit="%" />
        </div>

        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            <Icon name="grain" className="h-3.5 w-3.5" />
            {t("soil.availableNutrients")}
            <span className="font-normal normal-case text-faint">
              · {t("soil.shcSource")}{loc ? ` · ${loc}` : ""}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Stat label={t("soil.stat.availableN")} value={p.available_n_kg_ha} unit="kg/ha" rating={rating.n(p.available_n_kg_ha)} />
            <Stat label={t("soil.stat.availableP")} value={p.available_p_kg_ha} unit="kg/ha" rating={rating.p(p.available_p_kg_ha)} />
            <Stat label={t("soil.stat.availableK")} value={p.available_k_kg_ha} unit="kg/ha" rating={rating.k(p.available_k_kg_ha)} />
          </div>
          {p.available_p_kg_ha == null && (
            <p className="mt-1.5 text-[11px] text-faint">{t("soil.noShcRecord")}</p>
          )}
        </div>
      </div>
    </Card>
  );
}
