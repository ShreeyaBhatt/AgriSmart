import { createContext, createElement, useCallback, useContext, useEffect, useState } from "react";

const ThemeCtx = createContext({ theme: "light", setTheme: () => {}, toggleTheme: () => {} });
const KEY = "agrismart.theme";

function systemPrefersDark() {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

function applyTheme(theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    try {
      return localStorage.getItem(KEY) || (systemPrefersDark() ? "dark" : "light");
    } catch {
      return systemPrefersDark() ? "dark" : "light";
    }
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((t) => {
    setThemeState(t);
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* ignore */
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return createElement(ThemeCtx.Provider, { value: { theme, setTheme, toggleTheme } }, children);
}

export function useTheme() {
  return useContext(ThemeCtx);
}
