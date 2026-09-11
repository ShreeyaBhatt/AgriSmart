import { useEffect, useRef, useState } from "react";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import DiagnosisCard from "../components/DiagnosisCard.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";

export default function ScanFlow() {
  const t = useT();
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => {});
  }, []);
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
      setResult(await api.predict(file, plotId || undefined));
    } catch (e) {
      setError(e.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-lg font-bold tracking-tight text-ink">{t("scan.title")}</h1>
        <p className="text-sm text-muted">{t("scan.help")}</p>
      </div>

      <Card className="p-4">
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            pick(e.dataTransfer.files?.[0]);
          }}
          className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-line bg-canvas/40 px-4 py-8 text-center"
        >
          {preview ? (
            <img src={preview} alt="preview" className="max-h-56 rounded-lg object-contain ring-1 ring-line" />
          ) : (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                <Icon name="image" className="h-6 w-6" />
              </div>
              <p className="mt-2 text-sm text-muted">{t("scan.dropHint")}</p>
            </>
          )}

          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
            >
              <Icon name="image" className="h-3.5 w-3.5" /> {t("scan.chooseFile")}
            </button>
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted hover:bg-canvas">
              <Icon name="camera" className="h-3.5 w-3.5" /> {t("scan.camera")}
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
              className="mt-1 w-full rounded-lg border border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400"
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

        {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}

        <button
          onClick={analyse}
          disabled={!file || busy}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 active:scale-[0.99] disabled:bg-line disabled:text-faint"
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

      {result && <DiagnosisCard diagnosis={result} originalUrl={preview} />}
    </div>
  );
}
