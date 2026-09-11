import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useNavigate } from "react-router-dom";

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) {
      map.setView(points[0], 13);
    } else {
      map.fitBounds(points, { padding: [30, 30] });
    }
  }, [points, map]);
  return null;
}

export default function PlotsMap({ plots, height = "16rem" }) {
  const navigate = useNavigate();
  const points = plots.map((p) => [p.lat, p.lon]);

  return (
    <div className="overflow-hidden rounded-xl ring-1 ring-line" style={{ height }}>
      <MapContainer center={points[0] || [21.5, 78]} zoom={points.length ? 12 : 4} scrollWheelZoom>
        <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitBounds points={points} />
        {plots.map((p) => (
          <Marker
            key={p.id}
            position={[p.lat, p.lon]}
            eventHandlers={{ click: () => navigate(`/plots/${p.id}`) }}
          >
            <Tooltip>{p.name}</Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
