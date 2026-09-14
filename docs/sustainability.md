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
water_deficit%    = max(0, (water_recommended - water_used) / water_recommended * 100)
chemical_overuse% = max(0, (chemical_used - chemical_recommended) / chemical_recommended * 100)
crop_health%      = 100 - severity[disease_class]        # severity 0 if healthy / unknown-none

score = clamp(0..100, 100 - 0.4*water_overuse% - 0.4*water_deficit%
                       - 0.3*chemical_overuse% + 0.3*(crop_health% - 100))
```

`water_overuse%` and `water_deficit%` are mutually exclusive — usage is
either at/above the recommendation or below it, never both — so this is a
two-sided band around 100% of the recommendation, not a one-sided "only
penalise using too much" check. Under-watering is weighted the same (0.4)
as overuse: it isn't a lesser problem, it costs yield and crop health.
Applying ~90-110% of the recommendation lands within ~10 points either way
(a soft "optimal band"); severe under-watering is penalised as heavily as
the equivalent severe overuse.

`severity[...]` (health points removed by a diagnosed disease):

| disease keyword | points |
|---|---|
| late_blight | 60 |
| mosaic_virus / yellow_leaf_curl_virus | 55 |
| bacterial_spot / black_rot | 45 |
| esca | 40 |
| early_blight / gray_leaf_spot / leaf_blight | 35 |
| leaf_mold / common_rust / scab / powdery_mildew / target_spot | 30 |
| spider_mites | 25 |
| any other named disease | 30 |

## Bands

`≥ 80` excellent · `≥ 60` good · `≥ 40` fair · `< 40` poor.

The response echoes the formula string and returns 2–3 improvement tips based on
which term dragged the score down.

## `score`/`band` vs. `moisture_stress_risk` — read this before wiring up a UI

**`score`/`band` is an overall water + chemical + crop-health efficiency
grade, not a risk-free guarantee.** Because it blends three things into one
number, a real water-deviation problem doesn't always move the band. Example:
90 % of requirement applied is inside the soft optimal band and barely
touches the score at all, but a **30 % deviation** (used = 210 mm against a
300 mm requirement, say) only costs `0.4 * 30 = 12` points — nowhere near
enough to drop a clean input out of `excellent`. Shown alone, "Excellent"
next to a 30 %-under-watered field reads as "no problem here," which isn't
true.

So the response also carries a second, **deliberately separate** indicator
that is *never* blended into `score`/`band`:

| Field | Meaning |
|---|---|
| `water_deviation_pct` | signed version of the two fields above: negative = under-watering, positive = overuse, `0` = on target |
| `moisture_stress_risk` | `"none"` (\|deviation\| < 10 %) · `"moderate"` (10–25 %) · `"severe"` (≥ 25 %) — independent thresholds, not derived from the score |

**UI requirement:** show `moisture_stress_risk` as its own indicator, not as
a sub-detail of the score card that a user can miss. When it's `"moderate"`
or `"severe"`, that must be visible **even when `band` is `"excellent"` or
`"good"`** — the two are answering different questions (resource-use
efficiency vs. "is the crop stressed right now") and are expected to
disagree sometimes. Don't recolor or reword `band` based on
`moisture_stress_risk` — that would just move the same ambiguity somewhere
else; keep them visually distinct and let both be true at once.
