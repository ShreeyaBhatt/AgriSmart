import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { api } from "../api.js";
import { useLang, useT } from "../i18n/useT.js";
import { useLandUnit } from "../units/useLandUnit.js";

const LOCALE = { en: "en-IN", hi: "hi-IN", gu: "gu-IN", mr: "mr-IN", ta: "ta-IN", te: "te-IN", pa: "pa-IN" };
// MediaRecorder + local backend (faster-whisper) — 100% keyless, offline-capable sovereign speech
const MIC_SUPPORTED =
  typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
const MIC_MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
const MAX_RECORDING_MS = 15000;
const STORAGE_KEY = "agrismart.assistant.chat";

function renderInline(str) {
  if (!str) return "";
  const parts = [];
  let lastIdx = 0;
  const regex = /\*\*(.*?)\*\*/g;
  let match;
  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIdx) {
      parts.push(str.slice(lastIdx, match.index));
    }
    parts.push(
      <strong key={match.index} className="font-semibold text-ink">
        {match[1]}
      </strong>
    );
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < str.length) {
    parts.push(str.slice(lastIdx));
  }
  return parts.length > 0 ? parts : str;
}

function FormattedAnswer({ text }) {
  if (!text) return null;
  const blocks = text.split(/\n{2,}/);

  return (
    <div className="space-y-2 text-sm leading-relaxed text-ink">
      {blocks.map((block, bIdx) => {
        const lines = block.split("\n");
        const isBulletList = lines.every((l) => /^\s*[-*•]\s+/.test(l));
        const isNumberedList = lines.every((l) => /^\s*\d+\.\s+/.test(l));

        if (isBulletList) {
          return (
            <ul key={bIdx} className="my-1.5 space-y-1 pl-1">
              {lines.map((line, lIdx) => {
                const clean = line.replace(/^\s*[-*•]\s+/, "");
                return (
                  <li key={lIdx} className="flex items-start gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    <span>{renderInline(clean)}</span>
                  </li>
                );
              })}
            </ul>
          );
        }

        if (isNumberedList) {
          return (
            <ol key={bIdx} className="my-1.5 space-y-1 pl-1">
              {lines.map((line, lIdx) => {
                const match = line.match(/^\s*(\d+)\.\s+(.*)/);
                const num = match ? match[1] : `${lIdx + 1}`;
                const clean = match ? match[2] : line;
                return (
                  <li key={lIdx} className="flex items-start gap-2">
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] font-bold text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">
                      {num}
                    </span>
                    <span>{renderInline(clean)}</span>
                  </li>
                );
              })}
            </ol>
          );
        }

        if (lines.length === 1 && lines[0].startsWith("### ")) {
          return (
            <h4 key={bIdx} className="mt-2 text-sm font-bold text-ink">
              {renderInline(lines[0].replace(/^###\s+/, ""))}
            </h4>
          );
        }
        if (lines.length === 1 && lines[0].startsWith("## ")) {
          return (
            <h3 key={bIdx} className="mt-3 border-b border-line pb-1 text-base font-bold text-ink">
              {renderInline(lines[0].replace(/^##\s+/, ""))}
            </h3>
          );
        }

        return (
          <p key={bIdx}>
            {lines.map((l, lIdx) => (
              <span key={lIdx}>
                {lIdx > 0 && <br />}
                {renderInline(l)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

const STARTER_PROMPTS = [
  {
    icon: "camera",
    titleKey: "assistant.starterDiseaseTitle",
    promptKey: "assistant.starterDisease",
    borderColor: "hover:border-emerald-400",
  },
  {
    icon: "sun",
    titleKey: "assistant.starterWeatherTitle",
    promptKey: "assistant.starterWeather",
    borderColor: "hover:border-amber-400",
  },
  {
    icon: "flask",
    titleKey: "assistant.starterSoilTitle",
    promptKey: "assistant.starterSoil",
    borderColor: "hover:border-blue-400",
  },
  {
    icon: "sprout",
    titleKey: "assistant.starterConcoctionTitle",
    promptKey: "assistant.starterConcoction",
    borderColor: "hover:border-teal-400",
  },
];

export default function Assistant() {
  const t = useT();
  const { lang } = useLang();
  const { unit: landUnit, bighaRegion } = useLandUnit();
  const location = useLocation();
  const navigate = useNavigate();

  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState(location.state?.prefill || "");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speak, setSpeak] = useState(true);
  const [speakingIdx, setSpeakingIdx] = useState(null);
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [micError, setMicError] = useState("");
  const [voiceWarning, setVoiceWarning] = useState("");

  const endRef = useRef(null);
  const textareaRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const stopTimerRef = useRef(null);
  const audioRef = useRef(null);
  const playIdRef = useRef(0);
  const utteranceRef = useRef(null);

  useEffect(() => {
    api.listPlots().then(setPlots).catch(() => {});
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      /* ignore */
    }
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Stop any active speech and recording immediately whenever user switches the language
  useEffect(() => {
    stopAudio();
    stopRecording();
  }, [lang]);

  // Prime speech synthesis voice cache so getVoices() is ready without delay
  useEffect(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      const updateVoices = () => {
        window.speechSynthesis.getVoices();
      };
      updateVoices();
      window.speechSynthesis.addEventListener("voiceschanged", updateVoices);
      return () => {
        window.speechSynthesis.removeEventListener("voiceschanged", updateVoices);
      };
    }
  }, []);

  useEffect(() => {
    return () => {
      stopAudio();
      stopRecording();
      if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
      if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    };
  }, []);

  const stopAudio = () => {
    playIdRef.current++;
    if (audioRef.current) {
      try {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
        audioRef.current.onended = null;
        audioRef.current.onerror = null;
        audioRef.current.src = "";
      } catch {
        /* ignore */
      }
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
        window.speechSynthesis.resume?.();
      } catch {
        /* ignore */
      }
    }
    utteranceRef.current = null;
    setSpeakingIdx(null);
  };

  const fallbackSpeak = (cleanText, langCode, currentPlayId) => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      audioRef.current = null;
      setSpeakingIdx(null);
      setVoiceWarning(t("assistant.noVoiceForLang"));
      return;
    }

    try {
      window.speechSynthesis.resume?.();
      const targetLocale = LOCALE[langCode] || "en-IN";
      const voices = window.speechSynthesis.getVoices() || [];
      const matchedVoice = voices.find(
        (v) => v.lang === targetLocale || v.lang.toLowerCase().startsWith(langCode.toLowerCase())
      );

      const u = new SpeechSynthesisUtterance(cleanText);
      u.lang = targetLocale;
      if (matchedVoice) u.voice = matchedVoice;
      utteranceRef.current = u;

      u.onend = () => {
        if (playIdRef.current === currentPlayId) {
          utteranceRef.current = null;
          setSpeakingIdx(null);
        }
      };
      u.onerror = () => {
        if (playIdRef.current === currentPlayId) {
          utteranceRef.current = null;
          setSpeakingIdx(null);
          setVoiceWarning(t("assistant.noVoiceForLang"));
        }
      };

      window.speechSynthesis.speak(u);
    } catch (e) {
      audioRef.current = null;
      setSpeakingIdx(null);
      setVoiceWarning(t("assistant.noVoiceForLang"));
    }
  };

  const say = async (text, idx = null, targetLang = null) => {
    if (!text) return;
    if (idx === null && !speak) return;

    if (idx !== null && speakingIdx === idx) {
      stopAudio();
      return;
    }

    stopAudio();
    const currentPlayId = ++playIdRef.current;
    if (idx !== null) setSpeakingIdx(idx);
    setVoiceWarning("");

    const langCode = targetLang || lang || "en";
    const clean = text
      .replace(/[*#_`•\n]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 300);

    if (!clean) {
      setSpeakingIdx(null);
      return;
    }

    // Primary: Pre-warmed & Cached Server TTS (ultra-low latency ~2ms, clear natural speech for en + all Indic languages)
    try {
      const url = `/api/assistant/tts?text=${encodeURIComponent(clean)}&lang=${encodeURIComponent(langCode)}`;
      const audio = new Audio(url);
      audio.preload = "auto";
      audioRef.current = audio;

      audio.onended = () => {
        if (playIdRef.current === currentPlayId) {
          audioRef.current = null;
          setSpeakingIdx(null);
        }
      };

      audio.onerror = () => {
        if (playIdRef.current !== currentPlayId) return;
        fallbackSpeak(clean, langCode, currentPlayId);
      };

      await audio.play();
    } catch (err) {
      if (playIdRef.current !== currentPlayId) return;
      fallbackSpeak(clean, langCode, currentPlayId);
    }
  };

  const copyText = (text, idx) => {
    if (!text) return;
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopiedIdx(idx);
        setTimeout(() => setCopiedIdx(null), 2000);
      })
      .catch(() => {});
  };

  const clearChat = () => {
    if (messages.length === 0) return;
    if (window.confirm(t("assistant.clearConfirm"))) {
      setMessages([]);
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
      stopAudio();
    }
  };

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;

    stopAudio();

    const userMsg = { role: "user", text: q, timestamp: Date.now() };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);

    const historyPayload = messages
      .filter((m) => (m.role === "user" && m.text) || (m.role === "assistant" && m.answer))
      .slice(-8)
      .map((m) => ({
        role: m.role,
        content: m.role === "user" ? m.text : m.answer,
      }));

    try {
      const res = await api.assistant({
        question: q,
        plot_id: plotId || null,
        lang,
        land_unit: landUnit,
        bigha_region: landUnit === "bigha" ? bighaRegion : null,
        history: historyPayload,
      });
      const assistantMsg = {
        role: "assistant",
        ...res,
        timestamp: Date.now(),
      };
      setMessages([...nextMessages, assistantMsg]);
      if (speak) {
        say(res.speech_text || res.answer, nextMessages.length, res.lang || lang);
      }
    } catch (e) {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          answer: `${t("assistant.errorPrefix")} ${e.detail || e.message}`,
          grounded_on: [],
          engine: "Error Handler",
          timestamp: Date.now(),
        },
      ]);
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
    if (rec && rec.state !== "inactive") {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    }
    setRecording(false);
  };

  const startRecording = async () => {
    stopAudio();
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
        if (blob.size < 400) return;
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

  const toggleMic = () => {
    stopAudio();
    return recording ? stopRecording() : startRecording();
  };

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
              className="rounded-lg border border-line bg-canvas/60 px-2.5 py-1.5 text-xs text-ink outline-none transition focus:border-brand-400"
              title={t("assistant.noPlotContext")}
            >
              <option value="">{t("assistant.noPlotContext")}</option>
              {plots.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}

          <button
            type="button"
            onClick={() => {
              setSpeak((s) => {
                const next = !s;
                if (!next) stopAudio();
                return next;
              });
            }}
            className={`rounded-lg border p-2 text-xs font-medium transition ${
              speak
                ? "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-300"
                : "border-line text-muted hover:bg-canvas"
            }`}
            title={speak ? t("assistant.muteAnswers") : t("assistant.speakAnswers")}
          >
            <Icon name={speak ? "volume" : "volumeOff"} className="h-4 w-4" />
          </button>

          {messages.length > 0 && (
            <button
              type="button"
              onClick={clearChat}
              className="rounded-lg border border-line p-2 text-xs font-medium text-muted transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-900/20"
              title={t("assistant.clearChat")}
            >
              <Icon name="trash" className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Conversation Container */}
      <Card className="flex flex-1 flex-col overflow-hidden border-line">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
          {/* Welcome Screen / Prompt Starters */}
          {messages.length === 0 && (
            <div className="my-auto space-y-6 py-6 sm:py-8">
              <div className="space-y-2 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">
                  <Icon name="spark" className="h-6 w-6" />
                </div>
                <h2 className="text-base font-bold text-ink sm:text-lg">{t("assistant.promptStarterHeader")}</h2>
                <p className="mx-auto max-w-md text-xs text-muted sm:text-sm">{t("assistant.promptStarterSub")}</p>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {STARTER_PROMPTS.map((sp, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => send(t(sp.promptKey))}
                    className={`flex items-start gap-3 rounded-xl border border-line bg-surface p-3 text-left transition hover:bg-brand-50/40 hover:shadow-xs ${sp.borderColor} dark:hover:bg-brand-900/20`}
                  >
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                      <Icon name={sp.icon} className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-ink">{t(sp.titleKey)}</p>
                      <p className="line-clamp-2 text-[11px] text-muted">{t(sp.promptKey)}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
              {m.role === "user" ? (
                <div className="max-w-[85%] rounded-2xl rounded-br-xs bg-brand-700 px-4 py-2.5 text-sm leading-relaxed text-white shadow-xs">
                  <p className="whitespace-pre-wrap">{m.text}</p>
                </div>
              ) : (
                <div className="max-w-[90%] space-y-3 rounded-2xl rounded-bl-xs border border-line bg-surface p-4 shadow-xs">
                  {/* Bot Header */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/60 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded bg-brand-100 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">
                        <Icon name="spark" className="h-3 w-3" />
                      </span>
                      <span className="text-xs font-semibold text-ink">AgriSmart AI</span>
                    </div>

                    {/* Speech and Copy buttons */}
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => say(m.speech_text || m.answer, i, m.lang || lang)}
                        className={`inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] transition ${
                          speakingIdx === i
                            ? "bg-brand-100 font-semibold text-brand-800 dark:bg-brand-900/60 dark:text-brand-200"
                            : "text-muted hover:bg-canvas hover:text-ink"
                        }`}
                        title={speakingIdx === i ? t("assistant.stopListen") : t("assistant.listen")}
                      >
                        <Icon name={speakingIdx === i ? "volumeOff" : "volume"} className="h-3 w-3" />
                        <span>{speakingIdx === i ? t("assistant.stopListen") : t("assistant.listen")}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => copyText(m.answer, i)}
                        className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-muted transition hover:bg-canvas hover:text-ink"
                        title={copiedIdx === i ? t("assistant.copied") : t("assistant.copy")}
                      >
                        <Icon name={copiedIdx === i ? "check" : "copy"} className="h-3 w-3" />
                        <span>{copiedIdx === i ? t("assistant.copied") : t("assistant.copy")}</span>
                      </button>
                    </div>
                  </div>

                  {/* Formatted Markdown Answer */}
                  <FormattedAnswer text={m.answer} />

                  {/* Grounded Tags */}
                  {m.grounded_on?.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] text-muted">
                      <span className="flex items-center gap-1 text-faint">
                        <Icon name="shield" className="h-3 w-3 text-brand-600 dark:text-brand-400" />
                        {t("assistant.groundedOn")}
                      </span>
                      {m.grounded_on.map((g, gIdx) => (
                        <span
                          key={gIdx}
                          className="rounded-md border border-line bg-canvas/70 px-1.5 py-0.5 text-[10px] font-medium text-ink"
                        >
                          {g}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Interactive Action Shortcuts */}
                  {m.action_shortcuts?.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {m.action_shortcuts.map((sc, scIdx) => (
                        <button
                          key={scIdx}
                          type="button"
                          onClick={() => {
                            stopAudio();
                            navigate(sc.route);
                          }}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-brand-300 bg-brand-50/80 px-2.5 py-1.5 text-xs font-semibold text-brand-800 transition hover:border-brand-400 hover:bg-brand-100 dark:border-brand-700 dark:bg-brand-900/40 dark:text-brand-200"
                        >
                          <Icon name={sc.icon || "arrowRight"} className="h-3.5 w-3.5" />
                          <span>{sc.label}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Contextual Suggested Follow-ups */}
                  {m.suggested_followups?.length > 0 && i === messages.length - 1 && !busy && (
                    <div className="mt-3 space-y-1.5 border-t border-line/60 pt-2.5">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-muted">
                        <Icon name="spark" className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                        <span>{t("assistant.suggestedFollowups")}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {m.suggested_followups.map((fu, fIdx) => (
                          <button
                            key={fIdx}
                            type="button"
                            onClick={() => send(fu)}
                            className="rounded-full border border-brand-200 bg-canvas/80 px-3 py-1 text-xs text-ink transition hover:border-brand-500 hover:bg-brand-50 dark:border-line dark:hover:border-brand-600 dark:hover:bg-brand-900/30"
                          >
                            {fu}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Typing Bouncing Dots */}
          {busy && (
            <div className="flex justify-start">
              <div className="flex items-center gap-3 rounded-2xl rounded-bl-xs border border-line bg-surface px-4 py-3 shadow-xs">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand-600 text-white">
                  <Icon name="spark" className="h-3.5 w-3.5" />
                </div>
                <div className="flex items-center gap-1.5 py-1">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-brand-500 [animation-delay:-0.3s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-brand-500 [animation-delay:-0.15s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-brand-500" />
                </div>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        {/* Warnings / Errors */}
        {micError && (
          <p className="border-t border-line bg-rose-50 px-3 py-1.5 text-center text-xs text-rose-600 dark:bg-rose-950/30 dark:text-rose-400">
            {micError}
          </p>
        )}
        {voiceWarning && (
          <p className="border-t border-line bg-amber-50 px-3 py-1.5 text-center text-xs text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
            {voiceWarning}
          </p>
        )}

        {/* Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-center gap-2 border-t border-line bg-surface p-3"
        >
          {MIC_SUPPORTED ? (
            <button
              type="button"
              onClick={toggleMic}
              disabled={transcribing}
              title={recording ? t("assistant.stopRecording") : t("assistant.speakQuestion")}
              className={`rounded-lg border p-2.5 transition ${
                recording
                  ? "animate-pulse border-rose-300 bg-rose-50 text-rose-600 dark:bg-rose-900/30 dark:text-rose-400"
                  : transcribing
                    ? "border-amber-300 bg-amber-50 text-amber-600"
                    : "border-line text-muted hover:bg-canvas hover:text-ink"
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
              className="cursor-not-allowed rounded-lg border border-line p-2.5 text-faint"
            >
              <Icon name="mic" className="h-4 w-4" />
            </span>
          )}

          <input
            ref={textareaRef}
            type="text"
            value={input}
            onChange={(e) => {
              stopAudio();
              setInput(e.target.value);
            }}
            onFocus={stopAudio}
            onKeyDown={stopAudio}
            placeholder={t("assistant.placeholder")}
            disabled={busy}
            className="flex-1 rounded-lg border border-line bg-canvas/60 px-3.5 py-2 text-sm text-ink outline-none transition focus:border-brand-500 focus:bg-surface"
          />

          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint dark:disabled:bg-line/40"
          >
            <span>{t("action.ask")}</span>
            <Icon name="send" className="h-3.5 w-3.5" />
          </button>
        </form>
      </Card>
    </div>
  );
}
