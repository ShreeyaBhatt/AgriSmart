import { NavLink, Link, useNavigate } from "react-router-dom";
import clsx from "clsx";
import Icon from "./Icon.jsx";
import LanguageSwitcher from "./LanguageSwitcher.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { useT } from "../i18n/useT.js";
import { useSoilCheck } from "../lib/SoilCheckContext.jsx";
import { usePlotSoil } from "../lib/PlotSoilContext.jsx";

const NAV = [
  { to: "/", icon: "home", key: "nav.home", end: true },
  { to: "/scan", icon: "camera", key: "nav.scan" },
  { to: "/soil", icon: "layers", key: "nav.soil" },
  { to: "/weather", icon: "sun", key: "nav.weather" },
  { to: "/sustainability", icon: "chart", key: "nav.sustainability" },
  { to: "/assistant", icon: "chat", key: "nav.assistant" },
  { to: "/settings", icon: "user", key: "nav.settings" },
];

const BOTTOM = ["/", "/scan", "/weather", "/assistant", "/settings"];

export default function AppShell({ children }) {
  const t = useT();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { loading: soilLoading } = useSoilCheck();
  const { pendingPlot, soilStatus, dismiss } = usePlotSoil();

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
            <span className="text-sm font-bold tracking-tight text-ink">
              AgriSmart
            </span>
          </NavLink>

          <nav className="ml-4 hidden items-center gap-1 md:flex">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  clsx(
                    "relative flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
                    isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-muted hover:bg-canvas hover:text-ink"
                  )
                }
              >
                <Icon name={n.icon} className="h-4 w-4" />
                {t(n.key)}

                {n.to === "/soil" && soilLoading && (
                  <span className="absolute -right-1 -top-1 flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-500 opacity-75" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-brand-600" />
                  </span>
                )}

                {n.to === "/" &&
                  pendingPlot &&
                  soilStatus === "pending" && (
                    <span className="absolute -right-1 -top-1 flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-600" />
                    </span>
                  )}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <LanguageSwitcher />

            {user && (
              <button
                onClick={doLogout}
                title={t("action.logout")}
                className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
              >
                <Icon name="logout" className="h-4 w-4" />

                <span className="hidden items-center gap-1.5 sm:inline-flex">
                  {user.is_guest ? (
                    <span className="rounded-full bg-earth-400/20 px-1.5 py-0.5 text-[10px] font-semibold text-earth-600">
                      {t("nav.guestTag")}
                    </span>
                  ) : (
                    user.name || t("action.logout")
                  )}
                </span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5 pb-24 md:pb-8">
        {children}
      </main>

      {/* Plot soil fetch toast — shown on any page while polling */}
      {pendingPlot && (
        <div
          className={clsx(
            "fixed bottom-20 right-4 z-30 flex w-72 items-start gap-3 rounded-2xl border p-4 shadow-xl backdrop-blur-sm transition-all md:bottom-6",
            soilStatus === "ready"
              ? "border-emerald-200 bg-emerald-50/95 dark:border-emerald-800 dark:bg-emerald-950/90"
              : soilStatus === "failed"
              ? "border-amber-200 bg-amber-50/95 dark:border-amber-800 dark:bg-amber-950/90"
              : "border-brand-200 bg-surface/95 dark:border-brand-800"
          )}
        >
          {/* status icon / spinner */}
          {soilStatus === "ready" ? (
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/50">
              <Icon
                name="checkCircle"
                className="h-4 w-4 text-emerald-600 dark:text-emerald-400"
              />
            </span>
          ) : soilStatus === "failed" ? (
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/50">
              <Icon
                name="warning"
                className="h-4 w-4 text-amber-600 dark:text-amber-400"
              />
            </span>
          ) : (
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-900/40">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-300 border-t-brand-600" />
            </span>
          )}

          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-ink">
              {pendingPlot.name}
            </p>

            <p className="mt-0.5 text-[11px] text-muted">
              {soilStatus === "ready"
                ? t("plotNew.soilReady")
                : soilStatus === "failed"
                ? t("plotNew.soilFailed")
                : t("plotNew.soilFetchingBg")}
            </p>

            {soilStatus !== "pending" && (
              <Link
                to={`/plots/${pendingPlot.id}`}
                onClick={dismiss}
                className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:underline dark:text-brand-400"
              >
                {t("plotNew.skipToPlot")}
                <Icon name="arrowRight" className="h-3 w-3" />
              </Link>
            )}
          </div>

          <button
            onClick={dismiss}
            className="shrink-0 rounded-lg p-1 text-faint hover:bg-canvas"
            aria-label="Dismiss"
          >
            <Icon name="close" className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* bottom nav (mobile) */}
      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-md">
          {BOTTOM.map((to) => {
            const item = NAV.find((n) => n.to === to) || {
              to,
              icon: "user",
              key: "nav.settings",
            };

            return (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  clsx(
                    "relative flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition",
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

                    {to === "/" &&
                      pendingPlot &&
                      soilStatus === "pending" && (
                        <span className="absolute right-3 top-1 flex h-2.5 w-2.5">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-600" />
                        </span>
                      )}
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