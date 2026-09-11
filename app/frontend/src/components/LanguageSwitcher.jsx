import Icon from "./Icon.jsx";
import { LANGUAGES } from "../i18n/strings.js";
import { useLang } from "../i18n/useT.js";

export default function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  return (
    <label className="flex items-center gap-1 rounded-lg border border-line px-2 py-1.5 text-xs text-muted">
      <Icon name="globe" className="h-3.5 w-3.5" />
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value)}
        className="bg-transparent text-xs font-medium text-ink outline-none"
        aria-label="Language"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  );
}
