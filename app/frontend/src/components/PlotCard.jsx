import { Link } from "react-router-dom";
import Icon from "./Icon.jsx";
import { useT } from "../i18n/useT.js";
import { useLandUnit } from "../units/useLandUnit.js";
import { LAND_UNITS, formatArea } from "../units/convert.js";

export default function PlotCard({ plot }) {
  const t = useT();
  const { unit, bighaRegion } = useLandUnit();
  const unitLabel = t(LAND_UNITS.find((u) => u.code === unit)?.key ?? "unit.ha");
  const area = formatArea(plot.area_ha, unit, bighaRegion);
  const s = plot.soil_snapshot || {};
  return (
    <Link
      to={`/plots/${plot.id}`}
      className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3.5 transition hover:border-brand-200 hover:bg-brand-50/40"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
        <Icon name="map" className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-ink">{plot.name}</div>
        <div className="truncate text-xs text-muted">
          {s.texture_class ? `${s.texture_class}` : t("plot.soilPending")}
          {s.ph != null && ` · pH ${s.ph}`}
          {area != null && ` · ${area} ${unitLabel}`}
        </div>
      </div>
      <Icon name="chevronRight" className="h-4 w-4 text-faint" />
    </Link>
  );
}
