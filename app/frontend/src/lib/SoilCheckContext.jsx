import { createContext, useCallback, useContext, useState } from "react";
import { api } from "../api.js";

const SoilCheckCtx = createContext(null);

export function SoilCheckProvider({ children }) {
  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [season, setSeason] = useState("");
  const [textureOverride, setTextureOverride] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const analyse = useCallback(async (la, lo, s, tex = undefined, lang) => {
    if (la == null || lo == null) return;
    setLoading(true);
    setError("");
    setResult(null);
    // Explicit null clears override (fresh GPS analysis).
    // A string sets a new manual override.
    // undefined preserves existing override (for language toggle re-runs).
    const override = tex === null ? null : (tex !== undefined ? tex : textureOverride);
    setTextureOverride(override);
    try {
      const [profile, amendments, crops] = await Promise.all([
        api.soilLookup(la, lo, override),
        api.amendments(la, lo, override, lang),
        api.crops(la, lo, s || null, override, lang),
      ]);
      setResult({ profile, amendments, crops });
    } catch (e) {
      setError(e.detail || e.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [textureOverride]);

  return (
    <SoilCheckCtx.Provider
      value={{ lat, setLat, lon, setLon, season, setSeason, textureOverride, setTextureOverride, loading, error, result, analyse }}
    >
      {children}
    </SoilCheckCtx.Provider>
  );
}

export const useSoilCheck = () => useContext(SoilCheckCtx);
