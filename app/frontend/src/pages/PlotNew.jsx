import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";
import { useLandUnit } from "../units/useLandUnit.js";
import { LAND_UNITS, toHectares } from "../units/convert.js";

function ClickMarker({ pos, setPos }) {
  useMapEvents({ click: (e) => setPos([+e.latlng.lat.toFixed(5), +e.latlng.lng.toFixed(5)]) });
  return pos ? <Marker position={pos} /> : null;
}

// Soil status banner shown after plot is saved
function SoilBanner({ status, t }) {
  if (status === "ready") {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
        <Icon name="checkCircle" className="h-4 w-4 shrink-0" />
        <span className="font-medium">{t("plotNew.soilReady")}</span>
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
        <Icon name="warning" className="h-4 w-4 shrink-0" />
        <span>{t("plotNew.soilFailed")}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-brand-200 bg-brand-50/70 px-4 py-3 dark:border-brand-800 dark:bg-brand-900/20">
      <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
      <span className="text-sm text-brand-700 dark:text-brand-300">{t("plotNew.soilFetchingBg")}</span>
    </div>
  );
}

export default function PlotNew() {
  const t = useT();
  const navigate = useNavigate();
  const { unit, bighaRegion } = useLandUnit();
  const unitLabel = t(LAND_UNITS.find((u) => u.code === unit)?.key ?? "unit.ha");

  const [pos, setPos] = useState(null);
  const searchRef = useRef(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [mainCrop, setMainCrop] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedPlotId, setSavedPlotId] = useState(null);
  const [soilStatus, setSoilStatus] = useState("pending");
  const [patching, setPatching] = useState(false);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowResults(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!query.trim() || query.length < 3) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query.trim())}&limit=5&addressdetails=1`;
        const resp = await fetch(url, {
          headers: { "User-Agent": "AgriSmart-AI/0.1 (SIH-2026 hackathon)" },
        });
        if (resp.ok) {
          const data = await resp.json();
          setResults(
            data.map((r) => ({
              display: r.display_name,
              lat: parseFloat(r.lat),
              lon: parseFloat(r.lon),
            }))
          );
        }
        setShowResults(true);
      } catch (err) {
        console.error("Search failed:", err);
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [query]);

  const pickSearchResult = (r) => {
    setPos([+r.lat.toFixed(5), +r.lon.toFixed(5)]);
    setQuery(r.display.split(",")[0]);
    setShowResults(false);
    setResults([]);
  };

  const useGps = () => {
    navigator.geolocation?.getCurrentPosition(
      (p) => setPos([+p.coords.latitude.toFixed(5), +p.coords.longitude.toFixed(5)]),
      () => setError(t("plotNew.gpsError"))
    );
  };

  // Poll soil status every 3 s after save
  useEffect(() => {
    if (!savedPlotId || soilStatus !== "pending") return;
    const interval = setInterval(async () => {
      try {
        const status = await api.getSoilStatus(savedPlotId);
        if (status.ready) {
          setSoilStatus("ready");
          clearInterval(interval);
          setTimeout(() => navigate(`/plots/${savedPlotId}`), 1200);
        } else if (status.failed) {
          setSoilStatus("failed");
          clearInterval(interval);
        }
      } catch {
        // Ignore transient poll errors
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [savedPlotId, soilStatus, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    if (!pos || !name) return;
    setBusy(true);
    setError("");
    try {
      const plot = await api.createPlot({
        name,
        lat: pos[0],
        lon: pos[1],
        area_ha: toHectares(area, unit, bighaRegion),
        main_crop: mainCrop.trim() || null,
      });
      setSavedPlotId(plot.id);
      setSoilStatus(plot.soil_status ?? "pending");
      if (plot.soil_status === "ready") {
        navigate(`/plots/${plot.id}`);
      }
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  const patchDetails = async () => {
    if (!savedPlotId || patching) return;
    setPatching(true);
    try {
      await api.updatePlot(savedPlotId, {
        area_ha: toHectares(area, unit, bighaRegion),
        main_crop: mainCrop.trim() || null,
      });
    } catch {
      // Non-critical
    } finally {
      setPatching(false);
    }
  };

  const skipToPlot = async () => {
    await patchDetails();
    navigate(`/plots/${savedPlotId}`);
  };

  // Phase B: plot saved, soil fetching in background
  if (savedPlotId) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <h1 className="text-lg font-bold tracking-tight text-ink">{t("action.addPlot")}</h1>

        <SoilBanner status={soilStatus} t={t} />

        {soilStatus === "pending" && (
          <Card className="space-y-4 p-5">
            <p className="text-sm font-semibold text-ink">{t("plotNew.whileYouWait")}</p>

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted">
                {t("plotNew.areaPlaceholder").replace("{unit}", unitLabel)}
              </label>
              <input
                className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
                placeholder={t("plotNew.areaPlaceholder").replace("{unit}", unitLabel)}
                value={area}
                onChange={(e) => setArea(e.target.value)}
                onBlur={patchDetails}
                inputMode="decimal"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted">
                {t("plotNew.mainCropPlaceholder")}
              </label>
              <input
                className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
                placeholder={t("plotNew.mainCropPlaceholder")}
                value={mainCrop}
                onChange={(e) => setMainCrop(e.target.value)}
                onBlur={patchDetails}
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <p className="text-[11px] text-faint">{t("plotNew.autoSoilHint")}</p>
              <button
                type="button"
                onClick={skipToPlot}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline dark:text-brand-400"
              >
                {t("plotNew.skipToPlot")}
                <Icon name="arrowRight" className="h-3.5 w-3.5" />
              </button>
            </div>
          </Card>
        )}

        {soilStatus === "failed" && (
          <div className="flex justify-center">
            <Link
              to={`/plots/${savedPlotId}`}
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-800"
            >
              {t("plotNew.skipToPlot")}
              <Icon name="arrowRight" className="h-4 w-4" />
            </Link>
          </div>
        )}
      </div>
    );
  }

  // Phase A: initial create form
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-lg font-bold tracking-tight text-ink">{t("action.addPlot")}</h1>

      <Card className="overflow-hidden">
        {/* Search bar */}
        <div className="relative px-4 py-3 border-b border-line" ref={searchRef}>
          <div className="relative">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 pl-9 pr-8 text-xs text-ink outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-300/40"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setShowResults(true); }}
              onFocus={() => results.length > 0 && setShowResults(true)}
              placeholder={t("soil.searchPlaceholder")}
            />
            {searching && (
              <span className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin rounded-full border-2 border-faint/40 border-t-brand-500" />
            )}
          </div>
          {showResults && results.length > 0 && (
            <ul className="location-search-dropdown absolute inset-x-4 z-[9999] mt-1 max-h-52 overflow-y-auto rounded-xl border border-line bg-surface shadow-xl">
              {results.map((r, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => pickSearchResult(r)}
                    className="flex w-full items-start gap-2 px-3 py-2.5 text-left text-xs text-ink transition hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-brand-900/30"
                  >
                    <Icon name="location" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" />
                    <span className="line-clamp-2">{r.display}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="h-64">
          <MapContainer center={pos || [21.5, 78]} zoom={pos ? 13 : 4} scrollWheelZoom>
            <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <ClickMarker pos={pos} setPos={setPos} />
          </MapContainer>
        </div>

        <form onSubmit={submit} className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted">
              {pos ? `${pos[0]}, ${pos[1]}` : t("plotNew.tapMap")}
            </span>
            <button
              type="button"
              onClick={useGps}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
            >
              <Icon name="crosshair" className="h-3.5 w-3.5" /> {t("common.useMyLocation")}
            </button>
          </div>

          <input
            className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
            placeholder={t("plotNew.fieldNamePlaceholder")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
            placeholder={t("plotNew.areaPlaceholder").replace("{unit}", unitLabel)}
            value={area}
            onChange={(e) => setArea(e.target.value)}
            inputMode="decimal"
          />
          <input
            className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
            placeholder={t("plotNew.mainCropPlaceholder")}
            value={mainCrop}
            onChange={(e) => setMainCrop(e.target.value)}
          />

          {error && <p className="text-xs text-rose-600">{error}</p>}

          <button
            disabled={!pos || !name || busy}
            className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint"
          >
            {busy ? (
              <span className="inline-flex items-center justify-center gap-2">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                {t("plotNew.savePlot")}
              </span>
            ) : t("plotNew.savePlot")}
          </button>
          <p className="text-center text-[11px] text-faint">{t("plotNew.autoSoilHint")}</p>
        </form>
      </Card>
    </div>
  );
}
