import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useLang, useT } from "../i18n/useT.js";
import { useLandUnit } from "../units/useLandUnit.js";

const LOCALE = { en: "en-IN", hi: "hi-IN", gu: "gu-IN", mr: "mr-IN", ta: "ta-IN", te: "te-IN", pa: "pa-IN" };
// MediaRecorder + our own backend (faster-whisper) — not the browser's
// built-in SpeechRecognition, which always phones home to Google's cloud
// speech service even on "localhost". This way voice input only ever needs
// this app's own backend, so it keeps working with no internet at all.
const MIC_SUPPORTED =
  typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
const MIC_MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
const MAX_RECORDING_MS = 15000;

export default function Assistant() {
  const t = useT();
  const { lang } = useLang();
  const { unit: landUnit, bighaRegion } = useLandUnit();
  const location = useLocation();
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(location.state?.prefill || "");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speak, setSpeak] = useState(true);
  const [micError, setMicError] = useState("");
  const [voiceWarning, setVoiceWarning] = useState("");
  const endRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const stopTimerRef = useRef(null);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => {});
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);
  useEffect(() => {
    // release the mic if the user navigates away mid-recording
    return () => {
      if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
      if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    };
  }, []);

  const say = (text) => {
    if (!speak || !window.speechSynthesis) return;
    const target = LOCALE[lang] || "en-IN";
    // getVoices() can legitimately come back empty before the browser has
    // finished loading its voice list (no voiceschanged listener here to
    // keep this simple) — only treat an actually-populated list with no
    // match as "this device has nothing for Hindi/Gujarati", not a load race.
    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0 && !voices.some((v) => v.lang === target || v.lang.startsWith(target.slice(0, 2)))) {
      setVoiceWarning(t("assistant.noVoiceForLang"));
      return;
    }
    setVoiceWarning("");
    const u = new SpeechSynthesisUtterance(text);
    u.lang = target;
    u.onerror = () => setVoiceWarning(t("assistant.noVoiceForLang"));
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.assistant({
        question: q,
        plot_id: plotId || null,
        lang,
        land_unit: landUnit,
        bigha_region: landUnit === "bigha" ? bighaRegion : null,
      });
      setMessages((m) => [...m, { role: "assistant", ...res }]);
      say(res.answer);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", answer: `${t("assistant.errorPrefix")} ${e.detail || e.message}`, grounded_on: [] }]);
    } finally {
      setBusy(false);
    }
  };

  const stopRecording = () => {
    if (stopTimerRef.current) {
      clearTimeout(stopTimerRef.current);
      stopTimerRef.current = null;
    }
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  };

  const startRecording = async () => {
    if (!MIC_SUPPORTED || recording || transcribing) return;
    setMicError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MIC_MIME_CANDIDATES.find((c) => MediaRecorder.isTypeSupported?.(c)) || "";
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setRecording(false);
        const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
        chunksRef.current = [];
        if (blob.size < 500) return; // near-instant tap, nothing worth sending
        setTranscribing(true);
        try {
          const { text } = await api.transcribe(blob, lang);
          if (text?.trim()) {
            setInput(text);
            send(text);
          } else {
            setMicError(t("assistant.micNoSpeech"));
          }
        } catch (e) {
          setMicError(e.detail || e.message || t("assistant.micError"));
        } finally {
          setTranscribing(false);
        }
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
      stopTimerRef.current = setTimeout(stopRecording, MAX_RECORDING_MS);
    } catch (err) {
      setRecording(false);
      if (err.name === "NotAllowedError" || err.name === "SecurityError") {
        setMicError(t("assistant.micDenied"));
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        setMicError(t("assistant.micNoMic"));
      } else {
        setMicError(t("assistant.micError"));
      }
    }
  };

  const toggleMic = () => (recording ? stopRecording() : startRecording());

  return (
    /* Chat stays centered/single-column on purpose (long lines of chat text
       get harder to read, not more useful, on a wide screen) — just a bit
       wider than before so it's not as cramped as the other pages were. */
    <div className="mx-auto flex max-w-3xl flex-col" style={{ minHeight: "70vh" }}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-bold tracking-tight text-ink">{t("assistant.title")}</h1>
        <div className="flex items-center gap-2">
          {plots.length > 0 && (
            <select
              value={plotId}
              onChange={(e) => setPlotId(e.target.value)}
              className="rounded-lg border border-line bg-canvas/60 px-2 py-1.5 text-xs text-ink outline-none focus:border-brand-400"
            >
              <option value="">{t("assistant.noPlotContext")}</option>
              {plots.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => {
              setSpeak((s) => {
                const next = !s;
                if (!next && window.speechSynthesis) window.speechSynthesis.cancel();
                return next;
              });
            }}
            className={`rounded-lg border px-2 py-1.5 text-xs font-medium ${speak ? "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-300" : "border-line text-muted"}`}
            title={speak ? t("assistant.muteAnswers") : t("assistant.speakAnswers")}
          >
            <Icon name={speak ? "volume" : "volumeOff"} className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="py-10 text-center text-sm text-faint">
              {t("assistant.emptyHint")}
              {MIC_SUPPORTED ? ` ${t("assistant.emptyHintMic")}` : ""}
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-brand-700 text-white"
                    : "bg-canvas text-ink ring-1 ring-line"
                }`}
              >
                {m.answer ?? m.text}
                {m.role === "assistant" && m.grounded_on?.length > 0 && (
                  <div className="mt-1 text-[10px] text-faint">
                    {t("assistant.groundedOn")} {m.grounded_on.join(", ")}
                    {m.used_llm ? " · Gemini" : ` · ${t("assistant.knowledgeBase")}`}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-canvas px-3.5 py-2 text-sm text-faint ring-1 ring-line">…</div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {micError && (
          <p className="border-t border-line bg-rose-50 px-3 py-1.5 text-center text-xs text-rose-600">
            {micError}
          </p>
        )}
        {voiceWarning && (
          <p className="border-t border-line bg-earth-400/10 px-3 py-1.5 text-center text-xs text-earth-600">
            {voiceWarning}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-center gap-2 border-t border-line p-3"
        >
          {MIC_SUPPORTED ? (
            <button
              type="button"
              onClick={toggleMic}
              disabled={transcribing}
              title={recording ? t("assistant.stopRecording") : t("assistant.speakQuestion")}
              className={`rounded-lg border p-2 transition ${
                recording
                  ? "animate-pulse border-rose-300 bg-rose-50 text-rose-600"
                  : transcribing
                    ? "border-amber-300 bg-amber-50 text-amber-600"
                    : "border-line text-muted hover:bg-canvas"
              }`}
            >
              {transcribing ? (
                <span className="block h-4 w-4 animate-spin rounded-full border-2 border-amber-300 border-t-amber-600" />
              ) : (
                <Icon name="mic" className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span
              title={t("assistant.micUnsupported")}
              className="cursor-not-allowed rounded-lg border border-line p-2 text-faint"
            >
              <Icon name="mic" className="h-4 w-4" />
            </span>
          )}
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("assistant.placeholder")}
            className="flex-1 rounded-lg border border-line bg-canvas/60 px-3 py-2 text-sm text-ink outline-none focus:border-brand-400"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-lg bg-brand-700 px-3.5 py-2 text-sm font-semibold text-white disabled:bg-line disabled:text-faint"
          >
            {t("action.ask")}
          </button>
        </form>
      </Card>
    </div>
  );
}
