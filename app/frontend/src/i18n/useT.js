import { createContext, createElement, useCallback, useContext, useEffect, useState } from "react";
import { strings } from "./strings.js";

const LangCtx = createContext({ lang: "en", setLang: () => {} });
const KEY = "agrismart.lang";

export function LanguageProvider({ initial, children }) {
  const [lang, setLangState] = useState(() => {
    try {
      return localStorage.getItem(KEY) || initial || "en";
    } catch {
      return initial || "en";
    }
  });
  useEffect(() => {
    if (initial && initial !== lang) setLangState(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  const setLang = (l) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
  };
  return createElement(LangCtx.Provider, { value: { lang, setLang } }, children);
}

export function useLang() {
  return useContext(LangCtx);
}

export function useT() {
  const { lang } = useContext(LangCtx);
  return (key) => strings[lang]?.[key] ?? strings.en[key] ?? key;
}
