import Icon from "./Icon.jsx";
import { useTheme } from "../theme/useTheme.js";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggleTheme}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex items-center gap-1 rounded-lg border border-line px-2 py-1.5 text-xs text-muted transition hover:bg-canvas"
    >
      <Icon name={isDark ? "moon" : "sun"} className="h-3.5 w-3.5" />
    </button>
  );
}
