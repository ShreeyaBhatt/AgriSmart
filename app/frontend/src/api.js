// Central API client. In dev, Vite proxies /api and /uploads to the FastAPI backend
// (see vite.config.js). In a deployed build set VITE_API_BASE to the backend origin.
const ORIGIN = import.meta.env.VITE_API_BASE ?? "";
const BASE = `${ORIGIN}/api`;
const TOKEN_KEY = "agrismart.token";

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (t) => {
    try {
      t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = form; // FormData — let the browser set the boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (res.status === 401 && auth) {
    tokenStore.set(null);
    window.dispatchEvent(new Event("agrismart:unauthorized"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      // FastAPI returns 422 validation errors as {detail: [{loc, msg, type}, ...]}
      if (Array.isArray(body.detail)) {
        detail = body.detail.map((e) => e.msg || e.message || JSON.stringify(e)).join("; ");
      } else {
        detail = body.detail ?? detail;
      }
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // auth — phone + OTP, or guest
  requestOtp: (phone) => request("/auth/otp/request", { method: "POST", body: { phone }, auth: false }),
  verifyOtp: (phone, otp) =>
    request("/auth/otp/verify", { method: "POST", body: { phone, otp }, auth: false }),
  continueAsGuest: () => request("/auth/guest", { method: "POST", auth: false }),
  completeProfile: (b) => request("/auth/complete-profile", { method: "POST", body: b }),
  linkPhone: (phone, otp) => request("/auth/link-phone", { method: "POST", body: { phone, otp } }),
  updateProfile: (b) => request("/auth/profile", { method: "PATCH", body: b }),
  me: () => request("/auth/me"),

  // plots
  listPlots: () => request("/plots"),
  getPlot: (id) => request(`/plots/${id}`),
  createPlot: (b) => request("/plots", { method: "POST", body: b }),
  updatePlot: (id, b) => request(`/plots/${id}`, { method: "PATCH", body: b }),
  deletePlot: (id) => request(`/plots/${id}`, { method: "DELETE" }),
  refreshSoil: (id) => request(`/plots/${id}/refresh-soil`, { method: "POST" }),
  getSoilStatus: (id) => request(`/plots/${id}/soil-status`),
  timeline: (id, lang) => request(`/plots/${id}/timeline${lang ? `?lang=${lang}` : ""}`),

  // scan / diagnoses
  predict: (file, plotId, lang) => {
    const fd = new FormData();
    fd.append("file", file);
    if (plotId) fd.append("plot_id", plotId);
    if (lang) fd.append("lang", lang);
    return request("/predict", { method: "POST", form: fd });
  },
  listDiagnoses: (plotId, lang) => {
    const params = new URLSearchParams();
    if (plotId) params.set("plot_id", plotId);
    if (lang) params.set("lang", lang);
    const qs = params.toString();
    return request(`/diagnoses${qs ? `?${qs}` : ""}`);
  },
  getDiagnosis: (id, lang) => request(`/diagnoses/${id}${lang ? `?lang=${lang}` : ""}`),

  // logs
  logIrrigation: (b) => request("/irrigation", { method: "POST", body: b }),
  logAction: (b) => request("/actions", { method: "POST", body: b }),

  // module A (works without auth too)
  soilLookup: (lat, lon, textureOverride) => request("/soil/lookup", { method: "POST", body: { lat, lon, texture_override: textureOverride }, auth: false }),
  amendments: (lat, lon, textureOverride, lang) =>
    request("/recommend/amendments", { method: "POST", body: { lat, lon, texture_override: textureOverride, lang }, auth: false }),
  crops: (lat, lon, season, textureOverride, lang) =>
    request("/recommend/crops", { method: "POST", body: { lat, lon, season: season || null, texture_override: textureOverride, lang }, auth: false }),

  // module C / D / E
  weatherAdvice: (b) => request("/weather/advice", { method: "POST", body: b, auth: false }),
  sustainability: (b) => request("/sustainability/score", { method: "POST", body: b, auth: false }),
  assistant: (b) => request("/assistant/ask", { method: "POST", body: b }),
  transcribe: (audioBlob, lang) => {
    const fd = new FormData();
    fd.append("file", audioBlob, `voice.${audioBlob.type.includes("mp4") ? "mp4" : audioBlob.type.includes("ogg") ? "ogg" : "webm"}`);
    if (lang) fd.append("lang", lang);
    return request("/assistant/transcribe", { method: "POST", form: fd });
  },
};

// Upload paths from the API are like "/uploads/...": served at the origin, not under /api.
export const mediaUrl = (path) => (path ? `${ORIGIN}${path}` : null);
export { ApiError };
