import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import Stat from "./Stat.jsx";
import FractionBar from "./FractionBar.jsx";
import PhScale from "./PhScale.jsx";
import { rating } from "../lib/ratings.js";

function SourceBadge({ source }) {
  const offline = source?.startsWith("sample");
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1",
        offline ? "bg-amber-50 text-amber-700 ring-amber-200" : "bg-brand-50 text-brand-700 ring-brand-200"
      )}
      title={offline ? "SoilGrids was unreachable — showing the bundled sample profile" : "Live from SoilGrids 2.0"}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", offline ? "bg-amber-500" : "bg-brand-500")} />
      {source}
    </span>
  );
}

export default function SoilProfileCard({ profile: p }) {
  if (!p) return null;
  const u = p.uncertainty || {};
  const loc = [p.shc_district, p.shc_state].filter(Boolean).join(", ");

  return (
    <Card className="animate-fade-up overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line bg-gradient-to-b from-brand-50/60 to-transparent px-5 pt-4 pb-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-brand-700">
            <Icon name="layers" className="h-4 w-4" />
            Soil profile
          </div>
          <h2 className="mt-1 text-2xl font-bold capitalize tracking-tight text-ink">
            {p.texture_class || "Unknown texture"}
          </h2>
          <p className="text-xs text-muted">
            {p.wrb_class ? `${p.wrb_class} (WRB)` : "WRB class n/a"}
            {p.wrb_probability != null && (
              <span className="text-faint"> · p={p.wrb_probability}</span>
            )}
          </p>
        </div>
        <SourceBadge source={p.source} />
      </div>

      <div className="space-y-5 px-5 py-4">
        <div>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            Particle size · {p.depth_basis}
          </div>
          <FractionBar sand={p.sand_pct} silt={p.silt_pct} clay={p.clay_pct} />
        </div>

        <div className="rounded-xl border border-line bg-canvas/50 p-3.5">
          <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            <Icon name="flask" className="h-3.5 w-3.5" /> Soil reaction (pH)
          </div>
          <PhScale ph={p.ph} uncertainty={u.ph} />
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Org. C" value={p.organic_carbon_pct} unit="%" rating={rating.ocPct(p.organic_carbon_pct)}
            hint={p.organic_carbon_g_kg != null ? `${p.organic_carbon_g_kg} g/kg` : null} />
          <Stat label="Total N" value={p.total_nitrogen_g_kg} unit="g/kg" />
          <Stat label="CEC" value={p.cec_cmol_kg} unit="cmol/kg" rating={rating.cec(p.cec_cmol_kg)} />
          <Stat label="Bulk dens." value={p.bulk_density_kg_dm3} unit="kg/dm³" />
          <Stat label="Coarse frag." value={p.coarse_fragments_pct} unit="%" />
          <Stat label="Sand" value={p.sand_pct} unit="%" />
          <Stat label="Silt" value={p.silt_pct} unit="%" />
          <Stat label="Clay" value={p.clay_pct} unit="%" />
        </div>

        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            <Icon name="grain" className="h-3.5 w-3.5" />
            Available nutrients
            <span className="font-normal normal-case text-faint">
              · Soil Health Card{loc ? ` · ${loc}` : ""}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Available N" value={p.available_n_kg_ha} unit="kg/ha" rating={rating.n(p.available_n_kg_ha)} />
            <Stat label="Available P" value={p.available_p_kg_ha} unit="kg/ha" rating={rating.p(p.available_p_kg_ha)} />
            <Stat label="Available K" value={p.available_k_kg_ha} unit="kg/ha" rating={rating.k(p.available_k_kg_ha)} />
          </div>
          {p.available_p_kg_ha == null && (
            <p className="mt-1.5 text-[11px] text-faint">
              No Soil Health Card record for this district — get a lab soil test for exact N-P-K.
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
