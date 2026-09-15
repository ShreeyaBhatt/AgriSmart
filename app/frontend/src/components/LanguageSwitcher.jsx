import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { LANGUAGES } from "../i18n/strings.js";
import { useLang } from "../i18n/useT.js";

export default function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const current = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0];

  /* Close on outside click or Escape */
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    const onPointer = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  const choose = (code) => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setLang(code);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative" id="language-switcher">
      {/* Trigger button */}
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Select language"
        onClick={() => setOpen((o) => !o)}
        className={[
          "flex items-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs font-medium transition",
          "border-line bg-surface text-ink shadow-sm",
          "hover:border-brand-400 hover:text-brand-700",
          open ? "border-brand-400 text-brand-700" : "",
        ].join(" ")}
      >
        <Icon name="globe" className="h-3.5 w-3.5 shrink-0" />
        <span className="max-w-[64px] truncate">{current.label}</span>
        {/* Chevron */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={[
            "h-3 w-3 shrink-0 text-faint transition-transform duration-200",
            open ? "rotate-180" : "",
          ].join(" ")}
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          role="listbox"
          aria-label="Language options"
          className={[
            "absolute right-0 z-50 mt-1.5 w-48 origin-top-right",
            "rounded-xl border border-line bg-surface shadow-lg ring-1 ring-black/5",
            "animate-fade-up",
          ].join(" ")}
        >
          <div className="p-1.5 flex flex-col gap-0.5">
            {LANGUAGES.map((l) => {
              const active = l.code === lang;
              return (
                <button
                  key={l.code}
                  role="option"
                  aria-selected={active}
                  type="button"
                  onClick={() => choose(l.code)}
                  className={[
                    "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm font-medium transition",
                    active
                      ? "bg-brand-600 text-white"
                      : "text-ink hover:bg-canvas",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold tracking-tight ring-1",
                      active
                        ? "bg-white/20 text-white ring-white/30"
                        : "bg-brand-50 text-brand-700 ring-brand-200",
                    ].join(" ")}
                    aria-hidden="true"
                  >
                    {l.code.toUpperCase()}
                  </span>
                  <span>{l.label}</span>
                  {active && (
                    <Icon name="check" className="ml-auto h-3.5 w-3.5 shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
