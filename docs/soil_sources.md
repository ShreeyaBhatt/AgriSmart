# Soil data sources — Module A

AgriSmart pulls each farm's soil profile from **SoilGrids 2.0** by GPS coordinate, and
enriches it with **Soil Health Card** district averages for plant-available nutrients.
There is **no dependency on Bhuvan / any token-gated API.**

---

## 1. Primary source — SoilGrids 2.0 (ISRIC)

- **What:** global digital soil property maps at 250 m resolution, produced by ISRIC — World
  Soil Information from ~240,000 soil profile observations and ~400 environmental covariates
  via quantile random forest.
- **Licence:** CC-BY 4.0 (data and API). Free, no registration, no API key.
- **Citation:** Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B.,
  Ribeiro, E., and Rossiter, D. (2021). *SoilGrids 2.0: producing soil information for the
  globe with quantified spatial uncertainty.* SOIL, 7, 217–240.
  https://doi.org/10.5194/soil-7-217-2021
- **API base:** `https://rest.isric.org/soilgrids/v2.0/`
- **Fair use:** unauthenticated calls are rate-limited (~5 requests/minute). Call server-side,
  throttle, and cache every result into `plot.soil_snapshot`.

### 1a. Properties endpoint

```
GET https://rest.isric.org/soilgrids/v2.0/properties/query
    ?lon={lon}&lat={lat}
    &property=phh2o&property=soc&property=nitrogen
    &property=sand&property=silt&property=clay
    &property=cec&property=bdod&property=cfvo
    &depth=0-5cm&depth=5-15cm&depth=15-30cm
    &value=mean&value=uncertainty
```

Response: GeoJSON `Feature`; each property under
`properties.layers[].depths[].values.{mean,uncertainty}` with a
`properties.layers[].unit_measure` block carrying `d_factor`, `mapped_units`, `target_units`.

| Property  | Meaning                        | Mapped unit      | `d_factor` | Target unit    |
|-----------|--------------------------------|------------------|-----------|----------------|
| `phh2o`   | pH in water                    | pH ×10           | 10        | pH             |
| `soc`     | Soil organic carbon            | dg/kg            | 10        | g/kg           |
| `nitrogen`| Total nitrogen                 | cg/kg            | 100       | g/kg           |
| `sand`    | Sand (0.05–2 mm)               | g/kg             | 10        | %              |
| `silt`    | Silt (0.002–0.05 mm)           | g/kg             | 10        | %              |
| `clay`    | Clay (<0.002 mm)               | g/kg             | 10        | %              |
| `cec`     | Cation exchange capacity (pH 7)| mmol(c)/kg       | 10        | cmol(c)/kg     |
| `bdod`    | Bulk density of fine earth     | cg/cm³           | 100       | kg/dm³         |
| `cfvo`    | Coarse fragments (vol.)        | cm³/dm³ (‰)      | 10        | %              |

> Always divide by the `d_factor` **read from the response**, not a hardcoded constant — the
> table above is only a fallback.

### 1b. Classification endpoint

```
GET https://rest.isric.org/soilgrids/v2.0/classification/query
    ?lon={lon}&lat={lat}&number_classes=3
```

Returns the most probable **WRB (World Reference Base) Reference Soil Groups** with
probabilities, e.g. `wrb_class_probability: [["Vertisols", 0.62], ["Luvisols", 0.18], ...]`.
Store the top class + probability. Note WRB is an international taxonomy — it does **not** map
1:1 to Indian soil names (black / regur ≈ Vertisols, alluvial ≈ Fluvisols, red ≈ Luvisols /
Lixisols — indicative only).

---

## 2. Derived — USDA texture class

SoilGrids does not return a texture *name*. Derive it from the depth-weighted sand/silt/clay %
using the **USDA textural triangle** (12 classes: sand, loamy sand, sandy loam, loam, silt
loam, silt, sandy clay loam, clay loam, silty clay loam, sandy clay, silty clay, clay).
Implemented as a pure function `usda_texture(sand, silt, clay)` — a fixed set of inequality
rules, no external dependency. Reference boundaries: USDA-NRCS Soil Survey Manual, Ch. 3.

---

## 3. Depth aggregation

SoilGrids reports standard depth intervals. We use the plough / root zone and collapse the
three shallow layers to a single **0–30 cm depth-weighted mean**:

```
value_0_30 = (v[0-5] * 5 + v[5-15] * 10 + v[15-30] * 15) / 30
```

All six per-layer values (incl. 30–60, 60–100, 100–200 cm if requested) are kept verbatim in
`soil_snapshot.raw` for transparency.

---

## 4. Enrichment — Soil Health Card (nutrients)

SoilGrids has **total N** but not plant-available **P** or **K**. The Government of India
**Soil Health Card** scheme publishes district/block averages of available N, P₂O₅, K₂O
(and often S + micronutrients).

- Pre-load these averages into a `shc_reference` collection (loader:
  `scripts/load_shc_reference.py`), keyed by state + district (+ block where available).
- At lookup time: reverse-geocode `lat,lon` → district (Nominatim, already in the stack) →
  join on `shc_reference` → merge `available_n_kg_ha`, `available_p_kg_ha`, `available_k_kg_ha`.
- These fields are **nullable**. If the district is not in the reference set, the profile is
  still complete from SoilGrids; the amendments engine then advises an actual soil test.
- Source citation: Department of Agriculture & Farmers Welfare, *Soil Health Card* portal
  (soilhealth.dac.gov.in), district-level nutrient status.

---

## 5. Normalised `SoilProfile` (cached to `plot.soil_snapshot`)

| Field | Source |
|---|---|
| `source` | `"SoilGrids v2.0"` or `"SoilGrids v2.0 + SHC (<district>)"` or `"sample (offline)"` |
| `fetched_at`, `lat`, `lon` | request |
| `depth_basis` | `"0-30cm depth-weighted"` |
| `texture_class` | derived (USDA triangle) |
| `wrb_class`, `wrb_probability` | classification endpoint |
| `sand_pct`, `silt_pct`, `clay_pct` | `sand`/`silt`/`clay` ÷ d_factor |
| `ph` | `phh2o` ÷ d_factor |
| `organic_carbon_g_kg`, `organic_carbon_pct` | `soc` ÷ d_factor (÷10 again for %) |
| `total_nitrogen_g_kg` | `nitrogen` ÷ d_factor |
| `cec_cmol_kg` | `cec` ÷ d_factor |
| `bulk_density_kg_dm3` | `bdod` ÷ d_factor |
| `coarse_fragments_pct` | `cfvo` ÷ d_factor |
| `available_n_kg_ha`, `available_p_kg_ha`, `available_k_kg_ha` | SHC (nullable) |
| `shc_district` | reverse-geocode (nullable) |
| `uncertainty` | `value=uncertainty` per property (nullable) |
| `raw` | full SoilGrids properties + classification JSON |

---

## 6. Failure handling

`POST /soil/lookup {lat, lon}`:

1. SoilGrids `properties/query` + `classification/query` → normalise → enrich with SHC → cache.
2. If SoilGrids is unreachable / rate-limited → return the plot's last cached `soil_snapshot`
   if one exists.
3. Else return the bundled fixture `data/samples/soilgrids_sample.json` with
   `source: "sample (offline)"`.

The endpoint always returns HTTP 200 with a full profile — the demo never shows an error.
