import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";

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

export default function LocationPicker({ lat, lon, season, onChange, onSeason, onAnalyze, loading }) {
  const [latText, setLatText] = useState("");
  const [lonText, setLonText] = useState("");
  const [geoError, setGeoError] = useState("");

  useEffect(() => {
    setLatText(lat ?? "");
    setLonText(lon ?? "");
  }, [lat, lon]);

  const commitText = () => {
    const la = parseFloat(latText);
    const lo = parseFloat(lonText);
    if (!Number.isNaN(la) && !Number.isNaN(lo)) onChange(la, lo);
  };

  const useMyLocation = () => {
    setGeoError("");
    if (!navigator.geolocation) return setGeoError("Geolocation is not available in this browser.");
    navigator.geolocation.getCurrentPosition(
      (pos) => onChange(+pos.coords.latitude.toFixed(5), +pos.coords.longitude.toFixed(5)),
      (err) => setGeoError(err.message || "Could not get your location."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const hasPoint = lat != null && lon != null;

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-line px-5 pt-4 pb-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Icon name="location" className="h-4 w-4 text-brand-600" />
          Farm location
        </h2>
        <p className="mt-0.5 text-xs text-muted">Tap the map, use GPS, or type coordinates.</p>
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
                    : "bg-white text-muted ring-line hover:bg-brand-50 hover:text-brand-700"
                )}
              >
                {p.name}
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="text-[11px] font-medium text-faint">
            Latitude
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
            Longitude
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
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-canvas"
          >
            <Icon name="crosshair" className="h-3.5 w-3.5" />
            Use my location
          </button>
          <label className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-medium text-faint">
            Season
            <select
              className="rounded-lg border border-line bg-canvas/60 px-2 py-1.5 text-xs text-ink outline-none focus:border-brand-400"
              value={season}
              onChange={(e) => onSeason(e.target.value)}
            >
              <option value="">Any</option>
              <option value="kharif">Kharif</option>
              <option value="rabi">Rabi</option>
              <option value="zaid">Zaid</option>
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
              Analysing soil…
            </>
          ) : (
            <>
              <Icon name="sprout" className="h-4 w-4" />
              Analyse soil
            </>
          )}
        </button>
      </div>
    </Card>
  );
}
