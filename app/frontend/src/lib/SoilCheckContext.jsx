import { createContext, useCallback, useContext, useState } from "react";
import { api } from "../api.js";

const SoilCheckCtx = createContext(null);

export function SoilCheckProvider({ children }) {
  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [season, setSeason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const analyse = useCallback(async (la, lo, s) => {
    if (la == null || lo == null) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const [profile, amendments, crops] = await Promise.all([
        api.soilLookup(la, lo),
        api.amendments(la, lo),
        api.crops(la, lo, s || null),
      ]);
      setResult({ profile, amendments, crops });
    } catch (e) {
      setError(e.detail || e.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <SoilCheckCtx.Provider
      value={{ lat, setLat, lon, setLon, season, setSeason, loading, error, result, analyse }}
    >
      {children}
    </SoilCheckCtx.Provider>
  );
}

export const useSoilCheck = () => useContext(SoilCheckCtx);
