// Land-area unit conversion. Plots are always stored/transmitted as hectares
// (see app/backend/models/farm.py) — everything here is purely about how a
// farmer types and reads an area; the value that reaches the backend is
// always converted to hectares first, so nothing downstream needs to change.
//
// Keep the constants below in step with the backend's equivalent module,
// app/backend/services/units.py, if either changes.

export const LAND_UNITS = [
  { code: "ha", key: "unit.ha" },
  { code: "acre", key: "unit.acre" },
  { code: "bigha", key: "unit.bigha" },
  { code: "guntha", key: "unit.guntha" },
];

// Bigha was never standardised — it varies by state, and sometimes by
// district within a state. These are commonly-cited reference values, not
// legal figures; a farmer relying on this for anything official should
// still confirm the exact local figure with their revenue office.
export const BIGHA_REGIONS = [
  { code: "gujarat", key: "bighaRegion.gujarat", acrePerBigha: 0.4 },
  { code: "rajasthan_pucca", key: "bighaRegion.rajasthanPucca", acrePerBigha: 0.625 },
  { code: "rajasthan_kaccha", key: "bighaRegion.rajasthanKaccha", acrePerBigha: 0.4 },
  { code: "up", key: "bighaRegion.up", acrePerBigha: 0.625 },
  { code: "bihar", key: "bighaRegion.bihar", acrePerBigha: 0.625 },
  { code: "punjab", key: "bighaRegion.punjab", acrePerBigha: 0.5 },
  { code: "west_bengal", key: "bighaRegion.westBengal", acrePerBigha: 14400 / 43560 },
  { code: "assam", key: "bighaRegion.assam", acrePerBigha: 14400 / 43560 },
];
export const DEFAULT_BIGHA_REGION = "gujarat";

const HECTARE_PER_ACRE = 0.40468564224; // internationally defined acre
const GUNTHA_PER_ACRE = 40; // standard revenue unit — Maharashtra, Karnataka, ...

function acrePerBigha(region) {
  return (
    BIGHA_REGIONS.find((r) => r.code === region)?.acrePerBigha ??
    BIGHA_REGIONS.find((r) => r.code === DEFAULT_BIGHA_REGION).acrePerBigha
  );
}

/** Convert a stored hectare value into the given display unit. */
export function fromHectares(ha, unit, bighaRegion) {
  if (ha == null) return null;
  const acres = ha / HECTARE_PER_ACRE;
  if (unit === "acre") return acres;
  if (unit === "guntha") return acres * GUNTHA_PER_ACRE;
  if (unit === "bigha") return acres / acrePerBigha(bighaRegion);
  return ha;
}

/** Convert a value typed in the given display unit back into hectares for storage. */
export function toHectares(value, unit, bighaRegion) {
  if (value === "" || value == null) return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  if (unit === "ha") return n;
  let acres;
  if (unit === "acre") acres = n;
  else if (unit === "guntha") acres = n / GUNTHA_PER_ACRE;
  else if (unit === "bigha") acres = n * acrePerBigha(bighaRegion);
  else acres = n;
  return acres * HECTARE_PER_ACRE;
}

/** Rounded display value in the given unit — smaller units need fewer decimals. */
export function formatArea(ha, unit, bighaRegion) {
  const v = fromHectares(ha, unit, bighaRegion);
  if (v == null) return null;
  const decimals = unit === "bigha" || unit === "guntha" ? 1 : 2;
  return +v.toFixed(decimals);
}
