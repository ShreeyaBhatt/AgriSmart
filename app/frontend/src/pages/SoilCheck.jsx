import { useState } from "react";
import LocationPicker from "../components/LocationPicker.jsx";
import SoilProfileCard from "../components/SoilProfileCard.jsx";
import AmendmentsPanel from "../components/AmendmentsPanel.jsx";
import CropsPanel from "../components/CropsPanel.jsx";
import EmptyState from "../components/EmptyState.jsx";
import Icon from "../components/Icon.jsx";
import { ProfileSkeleton, PanelsSkeleton } from "../components/Skeleton.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";

export default function SoilCheck() {
  const t = useT();
  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [season, setSeason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const analyse = async () => {
    if (lat == null || lon == null) return;
    setLoading(true);
    setError("");
    try {
      const [profile, amendments, crops] = await Promise.all([
        api.soilLookup(lat, lon),
        api.amendments(lat, lon),
        api.crops(lat, lon, season),
      ]);
      setResult({ profile, amendments, crops });
    } catch (e) {
      setError(e.detail || e.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="mb-1 text-lg font-bold tracking-tight text-ink">{t("nav.soil")}</h1>
      <p className="mb-4 text-sm text-muted">
        Any GPS point → real soil from SoilGrids &amp; Soil Health Card. No login needed.
      </p>

      <div className="grid items-start gap-5 md:grid-cols-[minmax(0,360px)_1fr]">
        <div className="md:sticky md:top-20">
          <LocationPicker
            lat={lat}
            lon={lon}
            season={season}
            onChange={(la, lo) => {
              setLat(la);
              setLon(lo);
            }}
            onSeason={setSeason}
            onAnalyze={analyse}
            loading={loading}
          />
        </div>

        <div className="min-w-0 space-y-4">
          {error && (
            <div className="flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {loading && (
            <>
              <ProfileSkeleton />
              <PanelsSkeleton />
            </>
          )}
          {!loading && !result && !error && (
            <EmptyState icon="layers" title="No soil analysed yet"
              hint="Pick a farm on the map or a preset, then press Analyse soil." />
          )}
          {!loading && result && (
            <>
              <SoilProfileCard profile={result.profile} />
              <div className="grid gap-4 lg:grid-cols-2">
                <AmendmentsPanel report={result.amendments} />
                <CropsPanel rec={result.crops} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
