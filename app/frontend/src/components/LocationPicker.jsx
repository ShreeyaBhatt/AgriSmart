import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import { useT } from "../i18n/useT.js";

const FIELD =
  "w-full rounded-lg border border-line bg-canvas/60 px-3 py-2 text-sm text-ink outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-300/40";

function ClickToPlace({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

function Recenter({ lat, lon }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lon != null) map.setView([lat, lon], Math.max(map.getZoom(), 11), { animate: true });
  }, [lat, lon, map]);
  return null;
}

const PRESETS = [
  { name: "Vadodara", lat: 22.31, lon: 73.18 },
  { name: "Ludhiana", lat: 30.9, lon: 75.85 },
  { name: "Thrissur", lat: 10.5, lon: 76.2 },
];

// Debounced Nominatim search
function useLocationSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!query.trim() || query.trim().length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    timerRef.current = setTimeout(async () => {
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
      } catch {
        // Silently fail — user can still use manual input
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query]);

  return { query, setQuery, results, setResults, searching };
}

export default function LocationPicker({ lat, lon, season, onChange, onSeason, onAnalyze, loading, analyzeLabel, analyzingLabel }) {
  const t = useT();
  const [latText, setLatText] = useState("");
  const [lonText, setLonText] = useState("");
  const [geoError, setGeoError] = useState("");
  const { query, setQuery, results, setResults, searching } = useLocationSearch();
  const searchRef = useRef(null);
  const [showResults, setShowResults] = useState(false);

  useEffect(() => {
    setLatText(lat ?? "");
    setLonText(lon ?? "");
  }, [lat, lon]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowResults(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const commitText = () => {
    const la = parseFloat(latText);
    const lo = parseFloat(lonText);
    if (!Number.isNaN(la) && !Number.isNaN(lo)) onChange(la, lo);
  };

  const useMyLocation = () => {
    setGeoError("");
    if (!navigator.geolocation) return setGeoError(t("common.geoUnavailable"));
    navigator.geolocation.getCurrentPosition(
      (pos) => onChange(+pos.coords.latitude.toFixed(5), +pos.coords.longitude.toFixed(5)),
      (err) => setGeoError(err.message || t("common.geoError")),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const pickSearchResult = (r) => {
    onChange(+r.lat.toFixed(5), +r.lon.toFixed(5));
    setQuery(r.display.split(",")[0]); // show short name
    setShowResults(false);
    setResults([]);
  };

  const hasPoint = lat != null && lon != null;

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-line px-5 pt-4 pb-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Icon name="location" className="h-4 w-4 text-brand-600" />
          {t("soil.farmLocation")}
        </h2>
        <p className="mt-0.5 text-xs text-muted">{t("soil.locationHint")}</p>
      </div>

      {/* Search bar */}
      <div className="relative px-5 py-3.5" ref={searchRef}>
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
          <ul className="location-search-dropdown absolute inset-x-5 z-[9999] mt-1 max-h-52 overflow-y-auto rounded-xl border border-line bg-surface shadow-xl">
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

      <div className="h-60 sm:h-72">
        <MapContainer
          center={[hasPoint ? lat : 21.5, hasPoint ? lon : 78]}
          zoom={hasPoint ? 12 : 4}
          scrollWheelZoom
          zoomControl={false}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickToPlace onPick={(la, lo) => onChange(+la.toFixed(5), +lo.toFixed(5))} />
          <Recenter lat={hasPoint ? lat : null} lon={hasPoint ? lon : null} />
          {hasPoint && <Marker position={[lat, lon]} />}
        </MapContainer>
      </div>

      <div className="space-y-3 px-5 py-4">
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => {
            const active = hasPoint && Math.abs(lat - p.lat) < 1e-4 && Math.abs(lon - p.lon) < 1e-4;
            return (
              <button
                key={p.name}
                onClick={() => onChange(p.lat, p.lon)}
                className={clsx(
                  "rounded-full px-2.5 py-1 text-xs font-medium ring-1 transition",
                  active
                    ? "bg-brand-600 text-white ring-brand-600"
                    : "bg-surface text-muted ring-line hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-brand-900/30"
                )}
              >
                {p.name}
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="text-[11px] font-medium text-faint">
            {t("common.latitude")}
            <input
              className={FIELD + " mt-1"}
              value={latText}
              onChange={(e) => setLatText(e.target.value)}
              onBlur={commitText}
              placeholder="22.31"
              inputMode="decimal"
            />
          </label>
          <label className="text-[11px] font-medium text-faint">
            {t("common.longitude")}
            <input
              className={FIELD + " mt-1"}
              value={lonText}
              onChange={(e) => setLonText(e.target.value)}
              onBlur={commitText}
              placeholder="73.18"
              inputMode="decimal"
            />
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={useMyLocation}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-canvas"
          >
            <Icon name="crosshair" className="h-3.5 w-3.5" />
            {t("common.useMyLocation")}
          </button>
          <label className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-medium text-faint">
            {t("common.season")}
            <select
              className="rounded-lg border border-line bg-canvas/60 px-2 py-1.5 text-xs text-ink outline-none focus:border-brand-400"
              value={season}
              onChange={(e) => onSeason(e.target.value)}
            >
              <option value="">{t("common.seasonAny")}</option>
              <option value="kharif">{t("common.seasonKharif")}</option>
              <option value="rabi">{t("common.seasonRabi")}</option>
              <option value="zaid">{t("common.seasonZaid")}</option>
            </select>
          </label>
        </div>

        {geoError && <p className="text-xs text-rose-600">{geoError}</p>}

        <button
          onClick={onAnalyze}
          disabled={!hasPoint || loading}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-line disabled:text-faint"
        >
          {loading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              {analyzingLabel || t("soil.analysing")}
            </>
          ) : (
            <>
              <Icon name="sprout" className="h-4 w-4" />
              {analyzeLabel || t("soil.analyseSoil")}
            </>
          )}
        </button>
      </div>
    </Card>
  );
}