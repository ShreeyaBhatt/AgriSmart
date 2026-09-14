import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";
import { useLandUnit } from "../units/useLandUnit.js";
import { LAND_UNITS, toHectares } from "../units/convert.js";
import { usePlotSoil } from "../lib/PlotSoilContext.jsx";

function ClickMarker({ pos, setPos }) {
  useMapEvents({ click: (e) => setPos([+e.latlng.lat.toFixed(5), +e.latlng.lng.toFixed(5)]) });
  return pos ? <Marker position={pos} /> : null;
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
  const { startPolling } = usePlotSoil();

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
      // Hand off polling to the global context, then go straight to the plot.
      startPolling(plot);
      navigate(`/plots/${plot.id}`);
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };


  // Phase A: initial create form (only phase now — soil polling handled globally)
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
