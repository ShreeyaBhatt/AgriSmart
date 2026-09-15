import { useState, useEffect } from "react";
import clsx from "clsx";
import Card from "./Card.jsx";
import Icon from "./Icon.jsx";
import { api } from "../api.js";

const URGENCY_CONFIG = {
  critical: {
    badge: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800",
    dot: "bg-rose-500 animate-ping",
    label: "Immediate Action Required",
    border: "border-l-4 border-l-rose-500",
  },
  high: {
    badge: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
    dot: "bg-amber-500",
    label: "Urgent Advisory",
    border: "border-l-4 border-l-amber-500",
  },
  medium: {
    badge: "bg-yellow-50 text-yellow-800 border-yellow-200 dark:bg-yellow-950/40 dark:text-yellow-300 dark:border-yellow-800",
    dot: "bg-yellow-500",
    label: "Advisory",
    border: "border-l-4 border-l-yellow-500",
  },
  low: {
    badge: "bg-brand-50 text-brand-700 border-brand-200 dark:bg-brand-950/40 dark:text-brand-300 dark:border-brand-800",
    dot: "bg-brand-500",
    label: "Routine Observation",
    border: "border-l-4 border-l-brand-500",
  },
};

export default function AgentAdvisorCard({ plotId, lang = "en" }) {
  const [advisory, setAdvisory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [traceOpen, setTraceOpen] = useState(false);

  const fetchAdvisory = async () => {
    if (!plotId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.agentAdvisory(plotId, lang);
      setAdvisory(data);
    } catch (err) {
      setError(err.detail || err.message || "Failed to load agent advisory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdvisory();
  }, [plotId, lang]);

  if (loading) {
    return (
      <Card className="p-5">
        <div className="flex items-center gap-3">
          <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
          <div className="space-y-1">
            <p className="text-xs font-semibold text-ink">Autonomous Agentic Advisor</p>
            <p className="text-[11px] text-muted">Synthesizing weather, soil, pathology & planting telemetry...</p>
          </div>
        </div>
      </Card>
    );
  }

  if (error || !advisory) {
    return null;
  }

  const urgConfig = URGENCY_CONFIG[advisory.urgency] || URGENCY_CONFIG.low;
  const trace = advisory.decision_trace;
  const obs = trace?.observations || {};

  return (
    <Card className={clsx("overflow-hidden p-5 transition-all shadow-sm", urgConfig.border)}>
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300">
            <Icon name="spark" className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-ink">Autonomous Agronomic Advisor</h2>
            <p className="text-[11px] text-muted">
              {advisory.crop || "Crop"} · {advisory.growth_stage || "Active Stage"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
              urgConfig.badge
            )}
          >
            <span className="relative flex h-2 w-2">
              <span className={clsx("absolute inline-flex h-full w-full rounded-full opacity-75", urgConfig.dot)} />
              <span className={clsx("relative inline-flex h-2 w-2 rounded-full", urgConfig.dot.split(" ")[0])} />
            </span>
            {urgConfig.label}
          </span>
          <button
            onClick={fetchAdvisory}
            title="Re-evaluate Telemetry"
            className="rounded p-1 text-muted hover:bg-canvas hover:text-ink"
          >
            <Icon name="refresh" className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Main Advisory Narrative */}
      <div className="my-3 rounded-lg bg-canvas/60 p-3.5 text-xs leading-relaxed text-ink dark:bg-canvas/30">
        <p>{advisory.advice}</p>
      </div>

      {/* Prioritized Action Directives */}
      {trace?.action_plan && trace.action_plan.length > 0 && (
        <div className="mt-3 space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            Action Directives ({trace.action_plan.length})
          </h3>
          <div className="grid gap-2 sm:grid-cols-1">
            {trace.action_plan.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 rounded-lg border border-line bg-surface p-3 transition-colors hover:border-brand-300 dark:hover:border-brand-700"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 font-mono text-[11px] font-bold text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">
                  {item.priority}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="text-xs font-semibold text-ink">{item.directive}</span>
                    {item.timeframe && (
                      <span className="inline-flex items-center gap-1 rounded bg-canvas px-1.5 py-0.5 text-[10px] font-medium text-muted">
                        ⏱ {item.timeframe}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted leading-normal">{item.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Expandable Decision Trace & Audit Trail */}
      <div className="mt-4 border-t border-line pt-3">
        <button
          onClick={() => setTraceOpen(!traceOpen)}
          className="flex w-full items-center justify-between text-xs font-medium text-muted hover:text-ink"
        >
          <span className="flex items-center gap-1.5">
            <Icon name="flask" className="h-3.5 w-3.5 text-brand-600" />
            Decision Trace & Telemetry Audit ({trace?.rules_applied?.length || 0} rules checked)
          </span>
          <Icon
            name={traceOpen ? "chevronDown" : "chevronRight"}
            className="h-3.5 w-3.5 transition-transform"
          />
        </button>

        {traceOpen && (
          <div className="mt-3 space-y-3 rounded-lg bg-canvas/40 p-3 text-[11px] text-muted dark:bg-canvas/20">
            {/* Telemetry Grid */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded border border-line bg-surface p-2">
                <span className="block font-semibold text-ink">🌤 Weather Stream</span>
                <span>Rain: {obs.weather_forecast?.rain_probability_max_pct ?? 0}%</span>
                <span className="block">Precip: {obs.weather_forecast?.precipitation_sum_mm ?? 0} mm</span>
                <span className="block">Wind: {obs.weather_forecast?.wind_speed_max_kmh ?? 0} km/h</span>
              </div>
              <div className="rounded border border-line bg-surface p-2">
                <span className="block font-semibold text-ink">🔬 Pathology Stream</span>
                <span>Diagnosis: {obs.pathology?.disease_detected || "None"}</span>
                <span className="block">Severity: {obs.pathology?.severity || "N/A"}</span>
                <span className="block truncate" title={obs.pathology?.chemical_recipe}>
                  Recipe: {obs.pathology?.chemical_recipe ? "Verified" : "None"}
                </span>
              </div>
              <div className="rounded border border-line bg-surface p-2">
                <span className="block font-semibold text-ink">🌍 Soil Profile</span>
                <span>pH: {obs.soil?.ph ?? "N/A"}</span>
                <span className="block">Texture: {obs.soil?.texture_class || "N/A"}</span>
                <span className="block">OC: {obs.soil?.organic_carbon_pct ? `${obs.soil.organic_carbon_pct}%` : "N/A"}</span>
              </div>
              <div className="rounded border border-line bg-surface p-2">
                <span className="block font-semibold text-ink">🌱 Planting Stream</span>
                <span>Crop: {obs.planting?.crop || advisory.crop || "N/A"}</span>
                <span className="block">Stage: {obs.planting?.growth_stage || advisory.growth_stage || "N/A"}</span>
                <span className="block">DAP: {obs.planting?.days_after_planting ?? "N/A"}</span>
              </div>
            </div>

            {/* Resolved Conflicts */}
            {trace?.conflicts_detected && trace.conflicts_detected.length > 0 && (
              <div className="rounded border border-amber-200 bg-amber-50/50 p-2 text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
                <span className="font-semibold">⚠️ Multi-Stream Conflict Resolved:</span>
                <ul className="mt-1 list-inside list-disc space-y-0.5">
                  {trace.conflicts_detected.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Deterministic Rules Applied */}
            {trace?.rules_applied && trace.rules_applied.length > 0 && (
              <div>
                <span className="font-semibold text-ink">Deterministic Agronomic Rules Executed:</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {trace.rules_applied.map((rule, i) => (
                    <span
                      key={i}
                      className="rounded bg-surface px-2 py-0.5 font-mono text-[10px] text-brand-700 border border-brand-200 dark:bg-surface dark:text-brand-300 dark:border-brand-800"
                    >
                      {rule}
                    </span>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}
      </div>
    </Card>
  );
}
