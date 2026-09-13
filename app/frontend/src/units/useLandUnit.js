import { createContext, createElement, useContext, useState } from "react";
import { DEFAULT_BIGHA_REGION } from "./convert.js";

// Client-only preference, same shape as useLang()/useTheme() — a display
// convention, not farm data, so it lives in localStorage rather than the
// user's account (see app/backend/models/user.py for what is persisted).
const LandUnitCtx = createContext({
  unit: "ha",
  setUnit: () => {},
  bighaRegion: DEFAULT_BIGHA_REGION,
  setBighaRegion: () => {},
});
const UNIT_KEY = "agrismart.landUnit";
const REGION_KEY = "agrismart.bighaRegion";

export function LandUnitProvider({ children }) {
  const [unit, setUnitState] = useState(() => {
    try {
      return localStorage.getItem(UNIT_KEY) || "ha";
    } catch {
      return "ha";
    }
  });
  const [bighaRegion, setBighaRegionState] = useState(() => {
    try {
      return localStorage.getItem(REGION_KEY) || DEFAULT_BIGHA_REGION;
    } catch {
      return DEFAULT_BIGHA_REGION;
    }
  });

  const setUnit = (u) => {
    setUnitState(u);
    try {
      localStorage.setItem(UNIT_KEY, u);
    } catch {
      /* ignore */
    }
  };
  const setBighaRegion = (r) => {
    setBighaRegionState(r);
    try {
      localStorage.setItem(REGION_KEY, r);
    } catch {
      /* ignore */
    }
  };

  return createElement(
    LandUnitCtx.Provider,
    { value: { unit, setUnit, bighaRegion, setBighaRegion } },
    children
  );
}

export function useLandUnit() {
  return useContext(LandUnitCtx);
}
