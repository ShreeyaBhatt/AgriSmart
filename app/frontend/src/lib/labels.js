// Turn a model label like "Tomato___Late_blight" into "Tomato — Late blight".
export function prettyLabel(label) {
  if (!label) return "";
  if (!label.includes("___")) return label;
  const [crop, rest] = label.split("___");
  return `${crop.replace(/_/g, " ")} — ${rest.replace(/_/g, " ").trim()}`;
}

export const isHealthy = (label) => !!label && label.toLowerCase().endsWith("healthy");
export const isAbstain = (label) =>
  !label ||
  label.toLowerCase().startsWith("unclear") ||
  label.toLowerCase().startsWith("not a") ||
  label.toLowerCase().includes("abstain") ||
  label.toLowerCase().includes("unsupported");

