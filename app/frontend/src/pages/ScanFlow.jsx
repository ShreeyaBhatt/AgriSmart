import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import DiagnosisCard from "../components/DiagnosisCard.jsx";
import { api } from "../api.js";
import { useLang, useT } from "../i18n/useT.js";

// Decorative viewfinder corners — frame the whole photo only, never a
// sub-region: the model has no detection head, so this must never look
// like it's pointing at a specific lesion.
function ViewfinderCorners() {
  return (
    <>
      <span className="pointer-events-none absolute left-0 top-0 h-5 w-5 rounded-tl-md border-l-[3px] border-t-[3px] border-brand-500/70" />
      <span className="pointer-events-none absolute right-0 top-0 h-5 w-5 rounded-tr-md border-r-[3px] border-t-[3px] border-brand-500/70" />
      <span className="pointer-events-none absolute bottom-0 left-0 h-5 w-5 rounded-bl-md border-b-[3px] border-l-[3px] border-brand-500/70" />
      <span className="pointer-events-none absolute bottom-0 right-0 h-5 w-5 rounded-br-md border-b-[3px] border-r-[3px] border-brand-500/70" />
    </>
  );
}

export default function ScanFlow() {
  const t = useT();
  const { lang } = useLang();
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => { });
  }, []);
  // The label/precautions returned by /predict are localized server-side at
  // request time, so they don't move with the UI when the farmer switches
  // language afterwards — re-fetch the same diagnosis in the new language.
  useEffect(() => {
    if (!result) return;
    api.getDiagnosis(result.id, lang).then(setResult).catch(() => { });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);
  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pick = (f) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError("");
  };

  const analyse = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      setResult(await api.predict(file, plotId || undefined, lang));
    } catch (e) {
      setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-bold tracking-tight text-ink">{t("scan.title")}</h1>
        <p className="text-sm text-muted">{t("scan.help")}</p>
      </div>

      {/* Same left-form / right-results split as Soil check / Weather /
          Sustainability, so the diagnosis card has room to breathe on a
          wide window instead of everything being squeezed into one narrow
          centered column. */}
      <div className="grid items-start gap-5 md:grid-cols-[minmax(0,420px)_1fr]">
      <Card className="border-2 p-4 md:sticky md:top-20">
        <div
          onDragEnter={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            pick(e.dataTransfer.files?.[0]);
          }}
          className={clsx(
            "relative flex flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed px-4 py-14 sm:py-20 text-center transition-colors",
            dragOver ? "border-brand-400 bg-brand-500/5" : "border-line bg-canvas/40"
          )}
        >
          <div className="relative">
            {preview ? (
              <img src={preview} alt={t("scan.yourPhoto")} className="max-h-64 rounded-lg object-contain ring-2 ring-line" />
            ) : (
              <div className="p-8">
                <div className="mx-auto flex h-18 w-18 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 ring-2 ring-line">
                  <Icon name="image" className="h-9 w-9" />
                </div>
                <p className="mt-3 text-sm font-medium text-muted">{t("scan.dropHint")}</p>
              </div>
            )}
            <ViewfinderCorners />
            {busy && (
              <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg bg-ink/10">
                <div className="motion-reduce:hidden absolute inset-x-0 h-0.5 animate-scan-sweep bg-brand-400 shadow-[0_0_12px_2px_var(--color-brand-400)]" />
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border-2 border-line bg-surface px-4 text-sm font-semibold text-ink transition hover:border-brand-400 hover:text-brand-700"
            >
              <Icon name="image" className="h-4 w-4" /> {t("scan.chooseFile")}
            </button>
            <label className="inline-flex min-h-[44px] cursor-pointer items-center gap-2 rounded-lg border-2 border-line bg-surface px-4 text-sm font-semibold text-ink transition hover:border-brand-400 hover:text-brand-700">
              <Icon name="camera" className="h-4 w-4" /> {t("scan.camera")}
              <input
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => pick(e.target.files?.[0])}
              />
            </label>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </div>

        {plots.length > 0 && (
          <label className="mt-3 block text-[11px] font-medium text-faint">
            {t("scan.attachPlot")}
            <select
              value={plotId}
              onChange={(e) => setPlotId(e.target.value)}
              className="mt-1 w-full rounded-lg border-2 border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400"
            >
              <option value="">{t("common.none")}</option>
              {plots.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {error && (
          <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-rose-600">
            <Icon name="alert" className="h-4 w-4 shrink-0" /> {error}
          </p>
        )}

        <button
          onClick={analyse}
          disabled={!file || busy}
          className="mt-4 inline-flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 text-base font-bold text-white transition hover:bg-brand-800 active:scale-[0.99] disabled:bg-line disabled:text-faint"
        >
          {busy ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              {t("scan.analysing")}
            </>
          ) : (
            <>
              <Icon name="camera" className="h-4 w-4" /> {t("scan.title")}
            </>
          )}
        </button>
      </Card>

      <div className="min-w-0">
        {result && <DiagnosisCard diagnosis={result} originalUrl={preview} />}
      </div>
      </div>
    </div>
  );
}
