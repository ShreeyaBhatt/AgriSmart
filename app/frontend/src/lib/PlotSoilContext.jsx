import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const PlotSoilCtx = createContext(null);

/**
 * Tracks a single plot whose soil is being fetched in the background.
 * The polling loop lives here so it survives navigation between pages.
 */
export function PlotSoilProvider({ children }) {
  const [pendingPlot, setPendingPlot] = useState(null); // { id, name }
  const [soilStatus, setSoilStatus] = useState("pending"); // "pending" | "ready" | "failed"
  const intervalRef = useRef(null);

  // Clear any existing poll
  const clearPoll = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Start polling for a newly created plot
  const startPolling = useCallback(
    (plot) => {
      clearPoll();
      setPendingPlot({ id: plot.id, name: plot.name });
      setSoilStatus(plot.soil_status ?? "pending");

      if (plot.soil_status === "ready" || plot.soil_status === "failed") return;

      intervalRef.current = setInterval(async () => {
        try {
          const status = await api.getSoilStatus(plot.id);
          if (status.ready) {
            setSoilStatus("ready");
            clearPoll();
            // Auto-dismiss success banner after 6 s
            setTimeout(() => setPendingPlot(null), 6000);
          } else if (status.failed) {
            setSoilStatus("failed");
            clearPoll();
          }
        } catch {
          // Ignore transient errors
        }
      }, 3000);
    },
    [clearPoll]
  );

  // Dismiss the banner manually
  const dismiss = useCallback(() => {
    clearPoll();
    setPendingPlot(null);
  }, [clearPoll]);

  // Cleanup on unmount
  useEffect(() => clearPoll, [clearPoll]);

  return (
    <PlotSoilCtx.Provider value={{ pendingPlot, soilStatus, startPolling, dismiss }}>
      {children}
    </PlotSoilCtx.Provider>
  );
}

export const usePlotSoil = () => useContext(PlotSoilCtx);
