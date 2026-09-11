import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useLang, useT } from "../i18n/useT.js";

const SR =
  typeof window !== "undefined" &&
  (window.SpeechRecognition || window.webkitSpeechRecognition);
const LOCALE = { en: "en-IN", hi: "hi-IN", gu: "gu-IN" };

export default function Assistant() {
  const t = useT();
  const { lang } = useLang();
  const location = useLocation();
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(location.state?.prefill || "");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speak, setSpeak] = useState(true);
  const [micError, setMicError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => {});
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const say = (text) => {
    if (!speak || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = LOCALE[lang] || "en-IN";
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
      const res = await api.assistant({ question: q, plot_id: plotId || null, lang });
      setMessages((m) => [...m, { role: "assistant", ...res }]);
      say(res.answer);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", answer: `${t("assistant.errorPrefix")} ${e.detail || e.message}`, grounded_on: [] }]);
    } finally {
      setBusy(false);
    }
  };

  const ERROR_KEY = {
    "not-allowed": "assistant.micDenied",
    "service-not-allowed": "assistant.micDenied",
    "no-speech": "assistant.micNoSpeech",
    "audio-capture": "assistant.micNoMic",
    network: "assistant.micNetwork",
  };

  const mic = () => {
    if (!SR) return;
    setMicError("");
    const rec = new SR();
    rec.lang = LOCALE[lang] || "en-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onstart = () => setListening(true);
    rec.onend = () => setListening(false);
    rec.onerror = (e) => {
      setListening(false);
      setMicError(t(ERROR_KEY[e.error] || "assistant.micError"));
    };
    rec.onresult = (e) => {
      const said = e.results[0]?.[0]?.transcript;
      if (!said) return;
      setInput(said);
      send(said);
    };
    try {
      rec.start();
    } catch {
      // start() throws if a recognizer is already running (e.g. a fast double-tap)
      setListening(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col" style={{ minHeight: "70vh" }}>
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
            onClick={() => setSpeak((s) => !s)}
            className={`rounded-lg border px-2 py-1.5 text-xs font-medium ${speak ? "border-brand-200 bg-brand-50 text-brand-700" : "border-line text-muted"}`}
            title={t("assistant.speakAnswers")}
          >
            <Icon name="sun" className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="py-10 text-center text-sm text-faint">
              {t("assistant.emptyHint")}
              {SR ? ` ${t("assistant.emptyHintMic")}` : ""}
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
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-center gap-2 border-t border-line p-3"
        >
          {SR ? (
            <button
              type="button"
              onClick={mic}
              title={t("assistant.speakQuestion")}
              className={`rounded-lg border p-2 transition ${listening ? "animate-pulse border-rose-300 bg-rose-50 text-rose-600" : "border-line text-muted hover:bg-canvas"}`}
            >
              <Icon name="mic" className="h-4 w-4" />
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
