import { useState } from "react";
import clsx from "clsx";
import Card from "../components/Card.jsx";
import Icon from "../components/Icon.jsx";
import OtpInput from "../components/OtpInput.jsx";
import { LANGUAGES } from "../i18n/strings.js";
import { useLang, useT } from "../i18n/useT.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { useTheme } from "../theme/useTheme.js";
import { KNOWN_CROPS } from "../lib/crops.js";

const THEMES = [
  { value: "light", icon: "sun", key: "settings.light" },
  { value: "dark", icon: "moon", key: "settings.dark" },
];

const FIELD =
  "w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-300/40";

const BUTTON =
  "rounded-lg bg-brand-700 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-brand-800 disabled:bg-line disabled:text-faint";

/** Sets/edits the primary crop shown on the dashboard. Signup only ever
 * offered one shot at this for phone users, and a guest never saw the
 * picker at all — this is the only place either can set or change it now. */
function CropCard({ t, user }) {
  const { updateProfile } = useAuth();
  const known = user?.primary_crop && KNOWN_CROPS.includes(user.primary_crop);
  const [crop, setCrop] = useState(user?.primary_crop ? (known ? user.primary_crop : t("login.cropOther")) : "");
  const [cropOther, setCropOther] = useState(known ? "" : user?.primary_crop || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const value = crop === t("login.cropOther") ? cropOther : crop;
  const dirty = Boolean(value) && value !== (user?.primary_crop || "");

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await updateProfile({ primary_crop: value });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="text-[11px] font-medium uppercase tracking-wide text-faint">{t("login.cropLabel")}</div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {[...KNOWN_CROPS, t("login.cropOther")].map((c) => {
          const active = crop === c;
          return (
            <button
              key={c}
              type="button"
              onClick={() => setCrop(c)}
              className={clsx(
                "rounded-full px-2.5 py-1 text-xs font-medium ring-1 transition",
                active
                  ? "bg-brand-600 text-white ring-brand-600"
                  : "bg-surface text-muted ring-line hover:bg-brand-50 hover:text-brand-700"
              )}
            >
              {c}
            </button>
          );
        })}
      </div>
      {crop === t("login.cropOther") && (
        <input
          className={FIELD + " mt-2"}
          placeholder={t("login.cropOtherPlaceholder")}
          value={cropOther}
          onChange={(e) => setCropOther(e.target.value)}
        />
      )}
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
      <div className="mt-3 flex items-center gap-2">
        <button onClick={save} disabled={busy || !dirty} className={BUTTON}>
          {busy ? "…" : t("action.save")}
        </button>
        {saved && <Icon name="check" className="h-4 w-4 text-brand-600" />}
      </div>
    </Card>
  );
}

const isValidPhone = (phone) => {
  const digits = (phone || "").replace(/[\s\-()]/g, "").replace(/^\+/, "");
  return /^\d{10,15}$/.test(digits);
};

const formatAuthError = (err) => {
  const msg = err?.detail || err?.message || "";
  if (msg.includes("Value error") || msg.toLowerCase().includes("valid mobile number")) {
    return "Please enter a valid 10-digit mobile number.";
  }
  return msg;
};

/** Guest-only card for attaching a phone number to the current account, so
 * plots/scans survive a logout or a new device. */
function GuestUpgradeCard({ t, onLinked }) {
  const { requestOtp, linkPhone } = useAuth();
  const [step, setStep] = useState("idle"); // idle | phone | otp
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [demoOtp, setDemoOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const sendOtp = async (e) => {
    e.preventDefault();
    if (!isValidPhone(phone)) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const resp = await requestOtp(phone);
      setDemoOtp(resp.demo_otp || "");
      setOtp("");
      setStep("otp");
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await linkPhone(phone, otp);
      onLinked(phone);
    } catch (err) {
      // 409 = phone already belongs to a different account — worth a plain-
      // language message instead of the raw backend string.
      setError(err.status === 409 ? t("settings.guestUpgradePhoneTaken") : formatAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <Icon name="user" className="h-4.5 w-4.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-ink">{t("settings.guestUpgradeTitle")}</div>
          <p className="mt-0.5 text-xs text-muted">{t("settings.guestUpgradeDesc")}</p>

          {step === "idle" && (
            <button onClick={() => setStep("phone")} className={`${BUTTON} mt-3`}>
              {t("settings.guestUpgradeCta")}
            </button>
          )}

          {step === "phone" && (
            <form onSubmit={sendOtp} className="mt-3 space-y-2">
              <input
                className={FIELD}
                type="tel"
                inputMode="tel"
                maxLength={15}
                placeholder={t("login.phonePlaceholder")}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                autoFocus
                required
              />
              {error && <p className="text-xs text-rose-600">{error}</p>}
              <button disabled={busy} className={BUTTON}>
                {busy ? "…" : t("login.sendOtp")}
              </button>
            </form>
          )}

          {step === "otp" && (
            <div className="mt-3 space-y-2">
              {demoOtp && (
                <div className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700 ring-1 ring-brand-200">
                  {t("login.otpDemoHint")}{" "}
                  <span className="font-mono text-sm font-bold tracking-widest">{demoOtp}</span>
                </div>
              )}
              <form onSubmit={verify} className="space-y-2">
                <OtpInput value={otp} onChange={setOtp} />
                {error && <p className="text-center text-xs text-rose-600">{error}</p>}
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setStep("phone");
                      setError("");
                    }}
                    className="text-xs font-medium text-muted hover:text-ink"
                  >
                    {t("login.changeNumber")}
                  </button>
                  <button disabled={busy || otp.length < 4} className={BUTTON}>
                    {busy ? "…" : t("login.verify")}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function Settings() {
  const t = useT();
  const { lang, setLang } = useLang();
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();
  // Kept separate from user.is_guest — linking flips that to false right
  // away, which would hide this card before its own success message showed.
  const [linkedPhone, setLinkedPhone] = useState(null);

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

      <CropCard t={t} user={user} />

      {user?.is_guest && <GuestUpgradeCard t={t} onLinked={setLinkedPhone} />}

      {!user?.is_guest && linkedPhone && (
        <div className="flex items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-2.5 text-sm text-brand-700 ring-1 ring-brand-200">
          <Icon name="check" className="h-4 w-4 shrink-0" />
          {t("settings.guestUpgradeSuccess")} <span className="font-medium">{linkedPhone}</span>
        </div>
      )}

      <Card className="p-4">
        <div className="text-[11px] font-medium uppercase tracking-wide text-faint">{t("settings.language")}</div>
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

      <Card className="p-4">
        <div className="text-[11px] font-medium uppercase tracking-wide text-faint">{t("settings.appearance")}</div>
        <div className="mt-2 flex gap-2">
          {THEMES.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium ring-1 transition ${
                theme === opt.value
                  ? "bg-brand-600 text-white ring-brand-600"
                  : "bg-surface text-muted ring-line hover:bg-canvas"
              }`}
            >
              <Icon name={opt.icon} className="h-3.5 w-3.5" />
              {t(opt.key)}
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
