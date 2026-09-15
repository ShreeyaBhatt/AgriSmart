"""Backend settings. Env-overridable; sane defaults so it runs with zero config."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = .../AgriSmart  (this file is app/backend/config.py)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGRISMART_", env_file=str(REPO_ROOT / ".env"), extra="ignore")

    # --- SoilGrids ---
    soilgrids_base_url: str = "https://rest.isric.org/soilgrids/v2.0"
    soilgrids_timeout_s: float = 30.0
    # Courtesy gap between outbound SoilGrids requests. Kept small so an
    # interactive lookup stays snappy; raise it (env: AGRISMART_SOILGRIDS_MIN_INTERVAL_S)
    # for batch jobs to respect ISRIC fair-use.
    soilgrids_min_interval_s: float = 0.5
    # ISRIC's REST service is often slow / returns transient all-null payloads;
    # a couple of retries usually lands real data before the offline fallback.
    soilgrids_max_retries: int = 3
    # Hard ceiling on the whole SoilGrids phase of a lookup (properties +
    # classification, retries included). ISRIC's API can be slow — observed
    # ~27s on a normal day from South Asia; set comfortably above that.
    # Past this, give up and use the offline sample rather than let one
    # request's retries run unbounded; see soil_offline_cache_ttl_s below.
    soilgrids_deadline_s: float = 45.0

    # --- Nominatim (reverse geocode -> district for SHC enrichment) ---
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_timeout_s: float = 15.0
    # Nominatim usage policy requires a genuine identifying User-Agent.
    http_user_agent: str = "AgriSmart-AI/0.1 (SIH-2026 hackathon; contact: team@agrismart.local)"

    # --- CORS (frontend dev server / deployed SPA) ---
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Auth / DB — SQLite holds ML/farm data (plots, scans, ...); MongoDB holds accounts ---
    database_url: str = "sqlite+aiosqlite:///./agrismart.db"
    jwt_secret: str = "dev-secret-change-me"  # override AGRISMART_JWT_SECRET in production
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 14  # 14 days — farmers should not re-login often

    # --- MongoDB (accounts only) ---
    mongo_url: str = "mongodb://localhost:27017"  # "mongomock://..." swaps in an in-memory fake (tests)
    mongo_db_name: str = "agrismart"

    # --- OTP login ---
    # Every free-tier SMS route we evaluated turned out unusable for a
    # student-hackathon deployment: MSG91 has no free tier (pay-as-you-go
    # only), Twilio trial accounts can only text a phone number pre-verified
    # in the console (not real farmers' numbers), and Fast2SMS requires
    # project-URL verification before it will send. So on-screen display *is*
    # this deployment's delivery channel for now, gated by otp_show_code —
    # see services/otp.py's _deliver() for exactly where to plug in a real
    # provider (Twilio/MSG91/...) once one is available; nothing else needs
    # to change. This is still a real improvement over a fixed shared code:
    # each code is random per phone/request, held server-side hashed with an
    # expiry, one-shot (can't be replayed), and capped on wrong attempts —
    # unlike a single static value checked into source and valid forever for
    # every account.
    otp_ttl_s: int = 5 * 60
    otp_max_attempts: int = 5
    otp_resend_cooldown_s: int = 30
    otp_show_code: bool = True

    # --- Weather (Module C) ---
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_timeout_s: float = 15.0
    weather_cache_ttl_s: int = 60 * 15  # 15 min; forecasts don't move much faster than this
    weather_cache_precision: int = 3  # round lat/lon to N decimals (~110 m) for the cache key

    # --- GenAI assistant (Module E) / sustainability sanity-check (Module D) ---
    gemini_api_key: str = ""  # AGRISMART_GEMINI_API_KEY; empty -> offline/deterministic fallback
    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_s: float = 20.0

    # --- Three-Tier Hybrid Model & Local SLM (Module E & Presentation Layer) ---
    # "cards" = instant Tier 3 fallback (<2ms), zero model downloads (default for tests/offline)
    # "local" = Tier 2 in-process HuggingFace SLM on CPU
    # "gemini" = Google Gemini API
    # "auto" = uses local SLM if loaded/available, otherwise Tier 3 handbook cards
    llm_provider: str = "cards"
    local_model_id: str = "Qwen/Qwen2.5-0.5B-Instruct"
    local_model_device: str = "cpu"
    llm_timeout_s: float = 3.5  # strict SLA circuit-breaker ceiling
    llm_max_new_tokens: int = 160
    llm_circuit_breaker_max_fails: int = 3
    llm_circuit_breaker_reset_s: float = 60.0

    # --- Local speech-to-text for the mic button (Module E) ---
    # "tiny"/"base"/"small" — bigger = better multilingual accuracy, slower,
    # more RAM. Runs on this server; no audio ever reaches a cloud service.
    # "base" is too weak for Gujarati/Hindi (it can hallucinate transcripts into
    # an unrelated script); "small" is the practical minimum for reliable
    # Indic-language accuracy.
    whisper_model_size: str = "small"
    whisper_compute_type: str = "int8"  # CPU-friendly; use "int8_float16" on GPU

    # --- Caching ---
    soil_cache_ttl_s: int = 60 * 60 * 24 * 30  # 30 days; soil properties are ~static
    soil_cache_precision: int = 4  # round lat/lon to N decimals (~11 m) for the cache key
    # Profiling found the offline-sample fallback was never cached — only a
    # *successful* SoilGrids fetch was — so every request during an ISRIC
    # slowdown independently paid the full retry-and-timeout cost, with zero
    # relief even for the exact same coordinates queried twice in a row.
    # Short TTL because unlike real soil data this isn't something that
    # should be pinned for a month — worth retrying again soon in case
    # SoilGrids has recovered.
    soil_offline_cache_ttl_s: int = 60 * 5  # 5 min

    # --- Data files ---
    data_dir: Path = REPO_ROOT / "data"
    uploads_dir: Path = REPO_ROOT / "uploads"

    @property
    def shc_reference_dir(self) -> Path:
        return self.data_dir / "shc_reference"

    @property
    def disease_cards_path(self) -> Path:
        return self.data_dir / "disease_cards.json"

    @property
    def soilgrids_sample_path(self) -> Path:
        return self.data_dir / "samples" / "soilgrids_sample.json"

    @property
    def soil_amendments_path(self) -> Path:
        return self.data_dir / "soil_amendments.json"

    @property
    def crop_suitability_path(self) -> Path:
        return self.data_dir / "crop_suitability.json"

    @property
    def frontend_dist_dir(self) -> Path:
        return REPO_ROOT / "app" / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
