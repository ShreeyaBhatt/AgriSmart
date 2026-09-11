import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";

function ClickMarker({ pos, setPos }) {
  useMapEvents({ click: (e) => setPos([+e.latlng.lat.toFixed(5), +e.latlng.lng.toFixed(5)]) });
  return pos ? <Marker position={pos} /> : null;
}

export default function PlotNew() {
  const t = useT();
  const navigate = useNavigate();
  const [pos, setPos] = useState(null);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const useGps = () => {
    navigator.geolocation?.getCurrentPosition(
      (p) => setPos([+p.coords.latitude.toFixed(5), +p.coords.longitude.toFixed(5)]),
      () => setError("Could not get your location — tap the map instead.")
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
        area_ha: area ? Number(area) : null,
      });
      navigate(`/plots/${plot.id}`);
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-lg font-bold tracking-tight text-ink">{t("action.addPlot")}</h1>

      <Card className="overflow-hidden">
        <div className="h-64">
          <MapContainer center={pos || [21.5, 78]} zoom={pos ? 13 : 4} scrollWheelZoom>
            <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <ClickMarker pos={pos} setPos={setPos} />
          </MapContainer>
        </div>
        <form onSubmit={submit} className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted">
              {pos ? `${pos[0]}, ${pos[1]}` : "Tap the map to place your field"}
            </span>
            <button
              type="button"
              onClick={useGps}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
            >
              <Icon name="crosshair" className="h-3.5 w-3.5" /> Use my location
            </button>
          </div>
          <input
            className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
            placeholder="Field name (e.g. North field)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className="w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none focus:border-brand-400"
            placeholder="Area in hectares (optional)"
            value={area}
            onChange={(e) => setArea(e.target.value)}
            inputMode="decimal"
          />
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <button
            disabled={!pos || !name || busy}
            className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint"
          >
            {busy ? "Fetching soil…" : "Save plot"}
          </button>
          <p className="text-center text-[11px] text-faint">
            We'll pull this field's soil profile from SoilGrids automatically.
          </p>
        </form>
      </Card>
    </div>
  );
}
