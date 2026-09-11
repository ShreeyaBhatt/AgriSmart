# Module D — Sustainability Score

`POST /sustainability/score` — a **pure, published** function so the score is
fully reproducible. Implemented in `app/backend/services/sustainability.py`.

## Inputs

| Field | Meaning |
|---|---|
| `water_used_mm` | irrigation actually applied this season (mm) |
| `water_recommended_mm` | the crop's water requirement (mm) |
| `chemical_used_kg_ha` | fertiliser + pesticide active ingredient used (kg/ha) |
| `chemical_recommended_kg_ha` | recommended rate (kg/ha) |
| `disease_class` | latest diagnosis label, or `null` if healthy |

## Formula

```
water_overuse%    = max(0, (water_used - water_recommended) / water_recommended * 100)
chemical_overuse% = max(0, (chemical_used - chemical_recommended) / chemical_recommended * 100)
crop_health%      = 100 - severity[disease_class]        # severity 0 if healthy / unknown-none

score = clamp(0..100, 100 - 0.4*water_overuse% - 0.3*chemical_overuse% + 0.3*(crop_health% - 100))
```

`severity[...]` (health points removed by a diagnosed disease):

| disease keyword | points |
|---|---|
| late_blight | 60 |
| mosaic_virus / yellow_leaf_curl_virus | 55 |
| bacterial_spot / black_rot | 45 |
| esca | 40 |
| early_blight / gray_leaf_spot / leaf_blight | 35 |
| leaf_mould / common_rust / scab / powdery_mildew / target_spot | 30 |
| spider_mites | 25 |
| any other named disease | 30 |

## Bands

`≥ 80` excellent · `≥ 60` good · `≥ 40` fair · `< 40` poor.

The response echoes the formula string and returns 2–3 improvement tips based on
which term dragged the score down.
