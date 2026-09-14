import LocationPicker from "../components/LocationPicker.jsx";
import SoilProfileCard from "../components/SoilProfileCard.jsx";
import AmendmentsPanel from "../components/AmendmentsPanel.jsx";
import CropsPanel from "../components/CropsPanel.jsx";
import EmptyState from "../components/EmptyState.jsx";
import Icon from "../components/Icon.jsx";
import SoilLoadingExperience from "../components/SoilLoadingExperience.jsx";
import { useSoilCheck } from "../lib/SoilCheckContext.jsx";
import { useT } from "../i18n/useT.js";

export default function SoilCheck() {
  const t = useT();
  const { lat, setLat, lon, setLon, season, setSeason, loading, error, result, analyse } =
    useSoilCheck();

  const handleAnalyze = () => analyse(lat, lon, season);

  return (
    <div>
      <h1 className="mb-1 text-lg font-bold tracking-tight text-ink">{t("nav.soil")}</h1>
      <p className="mb-4 text-sm text-muted">{t("soil.pageHint")}</p>

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
            onAnalyze={handleAnalyze}
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
          {loading && <SoilLoadingExperience />}
          {!loading && !result && !error && (
            <EmptyState icon="layers" title={t("soil.emptyTitle")} hint={t("soil.emptyHint")} />
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
