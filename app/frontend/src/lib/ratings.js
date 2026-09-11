// Display-only rating bands. Kept in sync with data/soil_amendments.json thresholds.
// tone: "good" | "mid" | "low"  (low = needs attention)

const band = (v, rules) => {
  if (v === null || v === undefined) return null;
  for (const [max, label, tone] of rules) {
    if (max === null || v < max) return { label, tone };
  }
  return null;
};

export const rating = {
  ph: (v) =>
    v == null
      ? null
      : v < 5.5
        ? { label: "strongly acidic", tone: "low" }
        : v < 6.5
          ? { label: "slightly acidic", tone: "mid" }
          : v <= 7.5
            ? { label: "near neutral", tone: "good" }
            : v <= 8.5
              ? { label: "alkaline", tone: "mid" }
              : { label: "strongly alkaline", tone: "low" },
  ocPct: (v) => band(v, [[0.5, "low", "low"], [0.75, "medium", "mid"], [null, "adequate", "good"]]),
  cec: (v) => band(v, [[10, "low", "low"], [25, "moderate", "mid"], [null, "high", "good"]]),
  n: (v) => band(v, [[280, "low", "low"], [560, "medium", "mid"], [null, "high", "good"]]),
  p: (v) => band(v, [[10, "low", "low"], [25, "medium", "mid"], [null, "high", "good"]]),
  k: (v) => band(v, [[120, "low", "low"], [280, "medium", "mid"], [null, "high", "good"]]),
};

export const toneClasses = {
  good: { text: "text-brand-700", dot: "bg-brand-500", chip: "bg-brand-50 text-brand-700 ring-brand-200" },
  mid: { text: "text-amber-700", dot: "bg-amber-500", chip: "bg-amber-50 text-amber-700 ring-amber-200" },
  low: { text: "text-rose-700", dot: "bg-rose-500", chip: "bg-rose-50 text-rose-700 ring-rose-200" },
};

// pH position on a 3.5–9.5 scale, clamped to 0..1
export const phFraction = (v) => Math.max(0, Math.min(1, (v - 3.5) / 6));
