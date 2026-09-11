import { NavLink, useNavigate } from "react-router-dom";
import clsx from "clsx";
import Icon from "./Icon.jsx";
import LanguageSwitcher from "./LanguageSwitcher.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { useT } from "../i18n/useT.js";

const NAV = [
  { to: "/", icon: "home", key: "nav.home", end: true },
  { to: "/scan", icon: "camera", key: "nav.scan" },
  { to: "/soil", icon: "layers", key: "nav.soil" },
  { to: "/weather", icon: "sun", key: "nav.weather" },
  { to: "/sustainability", icon: "chart", key: "nav.sustainability" },
  { to: "/assistant", icon: "chat", key: "nav.assistant" },
];
const BOTTOM = ["/", "/scan", "/weather", "/assistant", "/settings"];

export default function AppShell({ children }) {
  const t = useT();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const doLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen">
      {/* top bar */}
      <header className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700 text-white ring-1 ring-brand-800/10 transition hover:scale-105">
              <Icon name="sprout" className="h-4 w-4" />
            </span>
            <span className="text-sm font-bold tracking-tight text-ink">AgriSmart</span>
          </NavLink>

          <nav className="ml-4 hidden items-center gap-1 md:flex">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
                    isActive ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas hover:text-ink"
                  )
                }
              >
                <Icon name={n.icon} className="h-4 w-4" />
                {t(n.key)}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <LanguageSwitcher />
            {user && (
              <button
                onClick={doLogout}
                title={t("action.logout")}
                className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
              >
                <Icon name="logout" className="h-4 w-4" />
                <span className="hidden items-center gap-1.5 sm:inline-flex">
                  {user.name?.split(" ")[0] || t("action.logout")}
                  {user.is_guest && (
                    <span className="rounded-full bg-earth-400/20 px-1.5 py-0.5 text-[10px] font-semibold text-earth-600">
                      {t("nav.guestTag")}
                    </span>
                  )}
                </span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5 pb-24 md:pb-8">{children}</main>

      {/* bottom nav (mobile) */}
      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-md">
          {BOTTOM.map((to) => {
            const item = NAV.find((n) => n.to === to) || { to, icon: "user", key: "nav.settings" };
            return (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  clsx(
                    "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition",
                    isActive ? "text-brand-700" : "text-faint"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon name={item.icon} className="h-5 w-5" />
                    {t(item.key)}
                    <span
                      className={clsx(
                        "mt-0.5 h-0.5 w-5 rounded-full transition",
                        isActive ? "bg-brand-700" : "bg-transparent"
                      )}
                    />
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
