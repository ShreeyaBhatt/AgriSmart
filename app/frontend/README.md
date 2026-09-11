# AgriSmart frontend

React 19 + Vite 6 + Tailwind v4 SPA. Login, My Farm dashboard, leaf‑scan flow,
per‑plot soil/crop/weather advice, sustainability score, and a voice farm assistant.

## Run

```bash
# backend first, from repo root:
python -m uvicorn app.backend.main:app --reload

# then, from app/frontend/:
npm install
npm run dev            # http://localhost:5173
```

The Vite dev server proxies all API paths to `http://127.0.0.1:8000` (override with
`VITE_API_TARGET`). For a deployed build set `VITE_API_BASE` to the backend origin.

## Layout

```
src/
  api.js               fetch client — attaches the JWT, redirects on 401
  App.jsx              routes (react-router-dom)
  auth/AuthContext.jsx token store + useAuth + <ProtectedRoute>
  i18n/                strings.js (en / hi / gu) + useT / useLang hooks
  lib/                 ratings.js (soil bands) · labels.js (pretty class names)
  pages/
    Login  Dashboard  ScanFlow  PlotNew  PlotDetail  SoilCheck
    Weather  Sustainability  Assistant  Settings
  components/
    AppShell  LanguageSwitcher  Card  Icon  Stat  EmptyState  Skeleton
    SoilProfileCard  AmendmentsPanel  CropsPanel  PhScale  FractionBar
    DiagnosisCard  ConfidenceBar  PlotCard  PlotsMap  Timeline  LogForms
    LocationPicker
```

## Design & animation

Tailwind v4 configured entirely in `src/index.css` via `@theme` (brand palette, Inter font,
`animate-fade-up`). Utility‑class styling; `clsx` for variants; shared `<Card>` surface.

| Component | Animation | How |
|---|---|---|
| Results reveal | fade + rise on data arrival | `animate-fade-up` (`@keyframes` in `@theme`) |
| Skeleton loaders | shimmer while loading | Tailwind `animate-pulse` |
| Scan / analyse buttons | spinner + label swap, `active:scale-[0.99]` | `animate-spin`, `transition` |
| Confidence bar | width fills to model confidence, colour‑stepped | width `%` transition |
| Crop score rings | SVG gauge fills to the 0–1 score | `stroke-dasharray` from score |
| pH spectrum | pointer slides to the measured pH on a gradient | `left: %` from `phFraction` |
| Particle‑size bar | sand/silt/clay segments sized by `%` | flex widths |
| Rating chips | low / moderate / good colour coding | `toneClasses` in `lib/ratings.js` |
| Interactive maps | click‑to‑pin, animated recenter, `fitBounds` | `react-leaflet` `useMap`/`useMapEvents` |
| Voice assistant | dictate the question, hear the answer | Web Speech API (`SpeechRecognition`, `speechSynthesis`) |
| Reduced motion | all of the above collapse to near‑instant | global `prefers-reduced-motion` rule |

**On‑theme candidate — typewriter / typing effect.** A `<Typewriter>` (char‑by‑char, blinking
caret, phrase cycling, reduced‑motion aware) for an "advisor is writing…" status line while
results load. Documented as a design idea; not currently in the codebase.
