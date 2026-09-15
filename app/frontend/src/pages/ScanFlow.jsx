import { useEffect, useRef, useState, useCallback } from "react";
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
  const cameraInputRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // Live Camera states
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraFacing, setCameraFacing] = useState("environment");
  const [cameraError, setCameraError] = useState("");

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => { });
  }, []);

  // Re-fetch diagnosis if language changes
  useEffect(() => {
    if (!result) return;
    api.getDiagnosis(result.id, lang).then(setResult).catch(() => { });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  // Handle preview object URL
  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Clean up camera stream on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
    setCameraLoading(false);
  }, []);

  const startCamera = useCallback(async (facing = cameraFacing) => {
    // If WebRTC is not supported, fall back directly to native camera input
    if (!navigator?.mediaDevices?.getUserMedia) {
      cameraInputRef.current?.click();
      return;
    }

    // Stop any existing stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setCameraActive(true);
    setCameraLoading(true);
    setCameraError("");
    setError("");

    try {
      const constraints = {
        video: {
          facingMode: { ideal: facing },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      };
      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = mediaStream;
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play().catch(() => {});
      }
      setCameraLoading(false);
    } catch (err) {
      console.warn("Live camera stream unavailable or permission denied:", err);
      stopCamera();

      let msgKey = "scan.cameraGenericError";
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        msgKey = "scan.cameraPermissionDenied";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        msgKey = "scan.cameraNotFound";
      }
      setCameraError(t(msgKey));
    }
  }, [cameraFacing, stopCamera, t]);

  const switchCamera = useCallback(() => {
    const nextFacing = cameraFacing === "environment" ? "user" : "environment";
    setCameraFacing(nextFacing);
    startCamera(nextFacing);
  }, [cameraFacing, startCamera]);

  const snapPhoto = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          const capturedFile = new File([blob], `leaf-scan-${Date.now()}.jpg`, {
            type: "image/jpeg",
          });
          stopCamera();
          pick(capturedFile);
        }
      },
      "image/jpeg",
      0.92
    );
  }, [stopCamera]);

  const pick = (f) => {
    if (!f) return;
    stopCamera();
    setCameraError("");
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

      <div className="grid items-start gap-5 md:grid-cols-[minmax(0,420px)_1fr]">
        <Card className="border-2 p-4 md:sticky md:top-20">
          {/* Live Camera Viewfinder */}
          {cameraActive ? (
            <div className="relative flex flex-col items-center justify-center overflow-hidden rounded-xl bg-black p-2">
              <div className="relative w-full overflow-hidden rounded-lg bg-black">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="h-64 sm:h-80 w-full rounded-lg object-cover"
                />
                <ViewfinderCorners />

                {cameraLoading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-white">
                    <span className="h-6 w-6 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  </div>
                )}

                {/* Floating Top Controls: Flip Camera & Close */}
                <div className="absolute right-2 top-2 flex items-center gap-1.5 z-10">
                  <button
                    type="button"
                    onClick={switchCamera}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur transition hover:bg-black/80 active:scale-95"
                    title={t("scan.flipCamera")}
                    aria-label={t("scan.flipCamera")}
                  >
                    <Icon name="refresh" className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={stopCamera}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur transition hover:bg-black/80 active:scale-95"
                    title={t("scan.closeCamera")}
                    aria-label={t("scan.closeCamera")}
                  >
                    <Icon name="close" className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Shutter Button Bar */}
              <div className="mt-4 mb-2 flex items-center justify-center gap-4">
                <button
                  type="button"
                  onClick={snapPhoto}
                  disabled={cameraLoading}
                  className="group relative flex h-16 w-16 items-center justify-center rounded-full border-4 border-white bg-brand-600 text-white shadow-lg transition active:scale-95 disabled:opacity-50"
                  title={t("scan.snapPhoto")}
                  aria-label={t("scan.snapPhoto")}
                >
                  <div className="h-11 w-11 rounded-full bg-white transition group-hover:scale-90" />
                </button>
              </div>
              <p className="text-xs font-medium text-white/80">{t("scan.snapPhoto")}</p>
            </div>
          ) : (
            /* File Dropzone & Preview */
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
                "relative flex flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed px-4 py-10 sm:py-16 text-center transition-colors",
                dragOver ? "border-brand-400 bg-brand-500/5" : "border-line bg-canvas/40"
              )}
            >
              <div className="relative">
                {preview ? (
                  <img
                    src={preview}
                    alt={t("scan.yourPhoto")}
                    className="max-h-64 rounded-lg object-contain ring-2 ring-line"
                  />
                ) : (
                  <div className="p-6">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 ring-2 ring-line dark:bg-brand-900/30">
                      <Icon name="camera" className="h-8 w-8" />
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

              {/* Action Buttons: Visually & Functionally Distinct */}
              <div className="mt-5 flex flex-wrap justify-center gap-2.5">
                {preview ? (
                  <>
                    <button
                      type="button"
                      onClick={() => startCamera()}
                      className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-brand-700 px-4 text-xs font-bold text-white shadow-sm transition hover:bg-brand-800 active:scale-[0.98]"
                    >
                      <Icon name="camera" className="h-4 w-4" /> {t("scan.retake")}
                    </button>
                    <button
                      type="button"
                      onClick={() => fileRef.current?.click()}
                      className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border-2 border-line bg-surface px-4 text-xs font-semibold text-ink transition hover:border-brand-400 hover:text-brand-700 active:scale-[0.98]"
                    >
                      <Icon name="image" className="h-4 w-4" /> {t("scan.chooseFile")}
                    </button>
                  </>
                ) : (
                  <>
                    {/* Primary Button: Live Camera Launch */}
                    <button
                      type="button"
                      onClick={() => startCamera()}
                      className="inline-flex min-h-[46px] items-center gap-2 rounded-xl bg-brand-700 px-5 text-sm font-bold text-white shadow-sm transition hover:bg-brand-800 active:scale-[0.98]"
                    >
                      <Icon name="camera" className="h-4 w-4" /> {t("scan.camera")}
                    </button>
                    {/* Secondary Button: Gallery / File Picker */}
                    <button
                      type="button"
                      onClick={() => fileRef.current?.click()}
                      className="inline-flex min-h-[46px] items-center gap-2 rounded-xl border-2 border-line bg-surface px-4 text-sm font-semibold text-ink transition hover:border-brand-400 hover:text-brand-700 active:scale-[0.98]"
                    >
                      <Icon name="image" className="h-4 w-4" /> {t("scan.chooseFile")}
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Camera Permission / Access Warning Banner */}
          {cameraError && (
            <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-amber-300 bg-amber-50 p-3.5 text-left text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200 animate-fade-up">
              <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <div className="min-w-0 flex-1">
                <p className="font-bold text-amber-900 dark:text-amber-100">
                  {t("scan.cameraPermissionTitle")}
                </p>
                <p className="mt-1 leading-relaxed text-amber-800 dark:text-amber-300">
                  {cameraError}
                </p>
                <div className="mt-2.5 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => startCamera()}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-amber-700 active:scale-95"
                  >
                    <Icon name="refresh" className="h-3.5 w-3.5" />
                    {t("scan.tryAgain")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCameraError("");
                      fileRef.current?.click();
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white/90 px-3 py-1.5 text-xs font-semibold text-amber-900 transition hover:bg-white dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-200 active:scale-95"
                  >
                    <Icon name="image" className="h-3.5 w-3.5" />
                    {t("scan.chooseFile")}
                  </button>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCameraError("")}
                className="text-amber-500 hover:text-amber-700 dark:text-amber-400"
                aria-label={t("scan.closeCamera")}
              >
                <Icon name="close" className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Hidden inputs: Dedicated File input vs Dedicated Camera capture input */}
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              pick(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => {
              pick(e.target.files?.[0]);
              e.target.value = "";
            }}
          />

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
            disabled={!file || busy || cameraActive}
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
