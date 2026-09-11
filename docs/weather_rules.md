# Module C — Weather rules

`POST /weather/advice {lat, lon, crop?, stage?, last_disease?}` fetches a 3‑day
forecast from **Open‑Meteo** (`api.open-meteo.com/v1/forecast`, free, no key) and
runs the rules below over a 24‑hour summary. Implemented in
`app/backend/services/weather.py`.

## Forecast summary fields

| Field | From |
|---|---|
| `rain_prob_24h_pct` | daily `precipitation_probability_max[0]` |
| `rain_sum_24h_mm` | sum of hourly `precipitation` over the next 24 h |
| `humidity_mean_24h_pct` | mean of hourly `relative_humidity_2m` over 24 h |
| `temp_max_c` / `temp_min_c` | daily `temperature_2m_max[0]` / `min` |
| `wind_max_kmh` | daily `wind_speed_10m_max[0]` |

`last_disease` is treated as **fungal** if its name contains any of:
`blight, mould/mold, mildew, rust, scab, rot, spot`.

## Rules (first matching irrigation rule + all applicable risk rules fire)

| # | Condition | Severity | Action |
|---|---|---|---|
| 1 | `rain_prob ≥ 60%` **or** `rain_24h ≥ 5 mm` | **act** | Delay irrigation — rain is coming |
| 2 | *(else)* `temp_max ≥ 34 °C` | watch | Irrigate at dawn/dusk to cut evaporation |
| 3 | fungal `last_disease` **and** `humidity ≥ 80%` | **act** | Spray preventively — fungal spread risk |
| 4 | *(else)* `humidity ≥ 85%` | watch | Scout for fungal disease, improve airflow |
| 5 | `temp_max ≥ 38 °C` | watch | Heat stress — mulch, no midday spraying |
| 6 | `temp_min ≤ 5 °C` | watch | Cold stress — protect seedlings, delay N |
| 7 | `wind_max ≥ 35 km/h` | watch | Delay spraying — drift risk |
| 8 | no rule fired | info | No weather action needed for 3 days |

Severity maps to the UI colour: `act` = red, `watch` = amber, `info` = green.
