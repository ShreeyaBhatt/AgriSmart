# AgriSmart backend

FastAPI + SQLite (SQLAlchemy async) for per‑farmer farm data, MongoDB (motor) for accounts,
phone+OTP JWT auth, the crop‑disease `/predict` API, Module A (soil), and Modules C / D / E.

## Run

```bash
pip install -r requirements.txt          # from repo root
python -m uvicorn app.backend.main:app --reload
```

Swagger at <http://127.0.0.1:8000/docs>. First run creates `agrismart.db` and `uploads/`.

## Layout

```
config.py        settings (env prefix AGRISMART_)
db.py            SQLite: async engine + session + init_db (farm data)
mongo.py         MongoDB: motor client + init_mongo_indexes (accounts)
auth.py          PyJWT tokens + get_current_user, backed by services/users.py
models/
  orm.py         SQLAlchemy tables: Plot, Planting, Diagnosis, IrrigationEvent, FarmerAction
  user.py        Pydantic User (MongoDB document shape)
  auth.py farm.py modules.py soil.py recommend.py   Pydantic request/response schemas
routers/
  auth plots plantings predict diagnoses logs soil recommend weather sustainability assistant
services/
  users            account repo over the Mongo `users` collection (phone/OTP, guest)
  soil_profile soilgrids_client soil_texture geocode shc   (Module A)
  recommend       (crop fit + amendments)
  weather         (Module C — Open-Meteo + rule engine)
  sustainability  (Module D — published formula)
  assistant       (Module E — RAG over data/disease_cards.json, Gemini or offline)
```

## Notes

- **Auth‑scoped:** every non‑auth query filters by `owner_id == current_user.id`
  (`tests/test_plots.py` proves two farmers can't see each other's data). `owner_id` is a plain
  string (a Mongo `User.id`) — not a SQL foreign key, since accounts live in a different database.
- **Login is phone + OTP, or guest** — no passwords. `AGRISMART_OTP_DEMO_CODE` (default
  `123456`) is accepted for any phone number; there's no SMS provider (see `routers/auth.py`).
- **`/predict`** lazily imports `model/` (torch) only when a scan comes in, and returns a
  friendly `503` if the model hasn't been trained yet — the rest of the API runs regardless.
- **Module E** uses Gemini when `AGRISMART_GEMINI_API_KEY` is set, otherwise answers directly
  from the disease‑card corpus (still grounded).
- Config via env (`.env` or shell), all optional — see `.env.example`.
