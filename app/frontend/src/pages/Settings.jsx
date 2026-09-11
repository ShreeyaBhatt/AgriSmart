import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import { LANGUAGES } from "../i18n/strings.js";
import { useLang, useT } from "../i18n/useT.js";
import { useAuth } from "../auth/AuthContext.jsx";

export default function Settings() {
  const t = useT();
  const { lang, setLang } = useLang();
  const { user, logout } = useAuth();

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-lg font-bold tracking-tight text-ink">{t("nav.settings")}</h1>

      <Card className="p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <Icon name="user" className="h-5 w-5" />
          </span>
          <div>
            <div className="text-sm font-semibold text-ink">{user?.name}</div>
            {user?.is_guest ? (
              <div className="text-xs text-muted">{t("settings.guestBadge")}</div>
            ) : (
              user?.phone && <div className="text-xs text-muted">{user.phone}</div>
            )}
            {user?.location_label && <div className="text-xs text-faint">{user.location_label}</div>}
          </div>
        </div>
      </Card>

      <Card className="p-4">
        <div className="text-[11px] font-medium uppercase tracking-wide text-faint">Language</div>
        <div className="mt-2 flex gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ring-1 transition ${
                lang === l.code
                  ? "bg-brand-600 text-white ring-brand-600"
                  : "bg-surface text-muted ring-line hover:bg-canvas"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </Card>

      <button
        onClick={logout}
        className="inline-flex items-center gap-1.5 rounded-xl border border-line px-4 py-2 text-sm font-medium text-rose-600 hover:bg-rose-50"
      >
        <Icon name="logout" className="h-4 w-4" /> {t("action.logout")}
      </button>
    </div>
  );
}
