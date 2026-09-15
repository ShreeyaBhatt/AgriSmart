import { useState } from "react";

import { useLocation, useNavigate } from "react-router-dom";

import clsx from "clsx";

import Icon from "../components/Icon.jsx";

import OtpInput from "../components/OtpInput.jsx";

import LanguageSwitcher from "../components/LanguageSwitcher.jsx";

import ThemeToggle from "../components/ThemeToggle.jsx";

import { useAuth } from "../auth/AuthContext.jsx";

import { useT } from "../i18n/useT.js";

import { KNOWN_CROPS } from "../lib/crops.js";

const FIELD =
  "w-full rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-sm text-ink outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-300/40";

const HERO_BULLETS = [
  { icon: "leaf", key: "login.heroBullet1" },
  { icon: "flask", key: "login.heroBullet2" },
  { icon: "globe", key: "login.heroBullet3" },
];

function Hero() {
  const t = useT();

  return (
    <div className="login-hero relative hidden overflow-hidden px-10 py-12 text-white md:flex md:w-[42%] md:flex-col md:justify-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(480px 320px at 15% 10%, rgba(255,255,255,0.16), transparent 60%), radial-gradient(420px 300px at 100% 100%, rgba(255,255,255,0.10), transparent 55%)",
        }}
      />

      <div className="relative">
        <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15">
          <Icon name="sprout" className="h-8 w-8" />
        </span>

        <h1 className="mt-6 text-2xl font-bold tracking-tight">
          {t("login.heroTitle")}
        </h1>

        <p className="mt-2 text-sm text-brand-100">
          {t("login.heroTagline")}
        </p>

        <ul className="mt-8 space-y-3">
          {HERO_BULLETS.map((b) => (
            <li
              key={b.key}
              className="flex items-center gap-2.5 text-sm text-brand-50"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/10">
                <Icon name={b.icon} className="h-3.5 w-3.5" />
              </span>

              {t(b.key)}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ModeStep({
  t,
  busy,
  onChooseLogin,
  onChooseSignup,
  onGuest,
}) {
  return (
    <div key="mode" className="animate-fade-up space-y-4">
      <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
        <Icon name="sprout" className="h-5 w-5" />
      </div>

      <h2 className="text-base font-semibold text-ink">
        {t("login.modeTitle")}
      </h2>

      <p className="text-xs text-muted">
        {t("login.modeSubtitle")}
      </p>

      <div className="space-y-2.5">
        {/* LOGIN */}
        <button
          type="button"
          onClick={onChooseLogin}
          disabled={busy}
          className="group flex w-full items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-left !text-ink transition hover:border-brand-300 hover:bg-brand-50 hover:!text-ink disabled:!text-faint"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 !text-brand-700">
            <Icon
              name="user"
              className="h-4.5 w-4.5 !text-brand-700"
            />
          </span>

          <span>
            <span className="block text-sm font-semibold !text-ink group-hover:!text-black">
              {t("login.loginOption")}
            </span>

            <span className="block text-xs !text-muted group-hover:!text-[#5a6a5f]">
              {t("login.loginOptionDesc")}
            </span>
          </span>
        </button>

        {/* SIGN UP */}
        <button
          type="button"
          onClick={onChooseSignup}
          disabled={busy}
          className="flex w-full items-center gap-3 rounded-xl bg-brand-700 px-4 py-3 text-left text-white transition hover:bg-brand-800 disabled:opacity-60"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10">
            <Icon name="sprout" className="h-4.5 w-4.5" />
          </span>

          <span>
            <span className="block text-sm font-semibold">
              {t("login.signupOption")}
            </span>

            <span className="block text-xs text-brand-100">
              {t("login.signupOptionDesc")}
            </span>
          </span>
        </button>
      </div>

      <div className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-wide text-faint">
        <span className="h-px flex-1 bg-line" />
        {t("login.guestOr")}
        <span className="h-px flex-1 bg-line" />
      </div>

      <button
        type="button"
        onClick={onGuest}
        disabled={busy}
        className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-canvas disabled:text-faint"
      >
        <Icon name="globe" className="h-4 w-4" />
        {t("login.guestCta")}
      </button>

      <p className="text-center text-[11px] text-faint">
        {t("login.guestHint")}
      </p>
    </div>
  );
}

function SignupNameStep({
  t,
  name,
  setName,
  busy,
  onSubmit,
  onBack,
}) {
  return (
    <div key="signupName" className="animate-fade-up space-y-4">
      <h2 className="text-base font-semibold text-ink">
        {t("login.signupNameTitle")}
      </h2>

      <form onSubmit={onSubmit} className="space-y-3">
        <input
          className={FIELD}
          placeholder={t("login.namePlaceholder")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          required
        />

        <button
          disabled={busy || !name.trim()}
          className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 active:scale-[0.99] disabled:bg-line disabled:text-faint"
        >
          {busy ? "…" : t("login.continue")}
        </button>
      </form>

      <button
        type="button"
        onClick={onBack}
        className="text-xs font-medium text-muted hover:text-ink"
      >
        {t("login.back")}
      </button>
    </div>
  );
}

function PhoneStep({
  t,
  phone,
  setPhone,
  busy,
  error,
  accountNotFound,
  onGoToSignup,
  onSend,
  onBack,
}) {
  return (
    <div key="phone" className="animate-fade-up space-y-4">
      <div className="mb-1 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
        <Icon name="user" className="h-5 w-5" />
      </div>

      <h2 className="text-base font-semibold text-ink">
        {t("login.phoneTitle")}
      </h2>

      <form onSubmit={onSend} className="space-y-3">
        <input
          className={FIELD}
          type="tel"
          inputMode="tel"
          maxLength={15}
          placeholder={t("login.phonePlaceholder")}
          value={phone}
          onChange={setPhone}
          autoFocus
          required
        />

        {accountNotFound ? (
          <div className="animate-fade-up rounded-xl border border-rose-200 bg-rose-50/80 p-3.5 text-xs text-rose-800">
            <div className="flex items-start gap-2.5">
              <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <div className="flex-1 space-y-2">
                <p className="font-medium leading-relaxed">
                  {error || t("login.noAccountFound")}
                </p>
                <div>
                  <button
                    type="button"
                    onClick={onGoToSignup}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-brand-800 active:scale-[0.98]"
                  >
                    <Icon name="sprout" className="h-3.5 w-3.5" />
                    {t("login.signUpCta")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          error && (
            <p className="text-xs text-rose-600">{error}</p>
          )
        )}

        <button
          disabled={busy}
          className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 active:scale-[0.99] disabled:bg-line disabled:text-faint"
        >
          {busy ? "…" : t("login.sendOtp")}
        </button>
      </form>

      <button
        type="button"
        onClick={onBack}
        className="text-xs font-medium text-muted hover:text-ink"
      >
        {t("login.back")}
      </button>
    </div>
  );
}

function OtpStep({
  t,
  phone,
  demoOtp,
  otp,
  setOtp,
  busy,
  error,
  onVerify,
  onChangeNumber,
  onResend,
}) {
  return (
    <div key="otp" className="animate-fade-up space-y-4">
      <h2 className="text-base font-semibold text-ink">
        {t("login.otpTitle")}
      </h2>

      <p className="text-xs text-muted">
        {t("login.otpSubtitle")}{" "}
        <span className="font-medium text-ink">{phone}</span>
      </p>

      {demoOtp && (
        <div className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700 ring-1 ring-brand-200">
          {t("login.otpDemoHint")}{" "}
          <span className="font-mono text-sm font-bold tracking-widest">
            {demoOtp}
          </span>
        </div>
      )}

      <form onSubmit={onVerify} className="space-y-4">
        <OtpInput value={otp} onChange={setOtp} />

        {error && (
          <p className="text-center text-xs text-rose-600">
            {error}
          </p>
        )}

        <button
          disabled={busy || otp.length !== 6}
          className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 active:scale-[0.99] disabled:bg-line disabled:text-faint"
        >
          {busy ? "…" : t("login.verify")}
        </button>
      </form>

      <div className="flex items-center justify-between text-xs">
        <button
          type="button"
          onClick={onChangeNumber}
          className="font-medium text-muted hover:text-ink"
        >
          {t("login.changeNumber")}
        </button>

        <button
          type="button"
          onClick={onResend}
          className="font-medium text-brand-700 hover:text-brand-800"
        >
          {t("login.resend")}
        </button>
      </div>
    </div>
  );
}

function ProfileStep({
  t,
  form,
  setForm,
  busy,
  error,
  onSubmit,
  skipName,
}) {
  const useGps = () => {
    navigator.geolocation?.getCurrentPosition(
      (p) =>
        setForm((f) => ({
          ...f,
          location: `${p.coords.latitude.toFixed(4)}, ${p.coords.longitude.toFixed(4)}`,
        })),
      () => {}
    );
  };

  return (
    <div key="profile" className="animate-fade-up space-y-4">
      <h2 className="text-base font-semibold text-ink">
        {t("login.profileTitle")}
      </h2>

      <form onSubmit={onSubmit} className="space-y-3">
        {!skipName && (
          <input
            className={FIELD}
            placeholder={t("login.namePlaceholder")}
            value={form.name}
            onChange={(e) =>
              setForm((f) => ({ ...f, name: e.target.value }))
            }
            autoFocus
            required
          />
        )}

        <div className="flex gap-2">
          <input
            className={FIELD}
            placeholder={t("login.locationPlaceholder")}
            value={form.location}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                location: e.target.value,
              }))
            }
            required
          />

          <button
            type="button"
            onClick={useGps}
            title={t("login.useMyLocation")}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs font-medium text-muted hover:bg-canvas"
          >
            <Icon name="crosshair" className="h-3.5 w-3.5" />
          </button>
        </div>

        <div>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
            {t("login.cropLabel")}
          </div>

          <div className="flex flex-wrap gap-1.5">
            {[...KNOWN_CROPS, t("login.cropOther")].map((crop) => {
              const active = form.crop === crop;

              return (
                <button
                  key={crop}
                  type="button"
                  onClick={() =>
                    setForm((f) => ({ ...f, crop }))
                  }
                  className={clsx(
                    "rounded-full px-2.5 py-1 text-xs font-medium ring-1 transition",
                    active
                      ? "bg-brand-600 text-white ring-brand-600"
                      : "bg-surface text-muted ring-line hover:bg-brand-50 hover:text-brand-700"
                  )}
                >
                  {crop}
                </button>
              );
            })}
          </div>

          {form.crop === t("login.cropOther") && (
            <input
              className={FIELD + " mt-2"}
              placeholder={t("login.cropOtherPlaceholder")}
              value={form.cropOther}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  cropOther: e.target.value,
                }))
              }
              required
            />
          )}
        </div>

        {error && (
          <p className="text-xs text-rose-600">{error}</p>
        )}

        <button
          disabled={busy || !form.name || !form.location || !form.crop}
          className="w-full rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-800 active:scale-[0.99] disabled:bg-line disabled:text-faint"
        >
          {busy ? "…" : t("login.finish")}
        </button>
      </form>
    </div>
  );
}

// Mirrors the backend's _normalize_phone (app/backend/models/auth.py) so an
// obviously-bad number is caught before it ever reaches the network — the
// backend still re-validates and is the source of truth either way.
const isValidPhone = (phone) => {
  const raw = (phone || "").trim();
  if (!raw || raw.startsWith("-")) return false; // no negative numbers
  if (!/^\+?[\d\s\-()]+$/.test(raw)) return false; // letters/symbols beyond the usual formatting chars

  let digits = raw.replace(/\D/g, "").replace(/^0+/, ""); // strip formatting + trunk-prefix zeros
  if (digits.length > 10 && digits.startsWith("91")) digits = digits.slice(2); // country code

  if (!/^\d{10}$/.test(digits)) return false; // exactly 10 digits, no more, no less
  if (new Set(digits).size === 1) return false; // reject "1111111111"-style fakes
  return true;
};

const formatAuthError = (err) => {
  let msg = err?.detail || err?.message || "";

  if (typeof msg !== "string") {
    msg = JSON.stringify(msg);
  }

  if (msg.startsWith("Value error, ")) {
    msg = msg.slice("Value error, ".length);
  } else if (msg.startsWith("Value error: ")) {
    msg = msg.slice("Value error: ".length);
  }

  if (
    msg.includes("Value error") ||
    msg.toLowerCase().includes("valid mobile number") ||
    msg.toLowerCase().includes("10-digit")
  ) {
    return "Please enter a valid 10-digit mobile number.";
  }

  return msg;
};

export default function Login() {
  const t = useT();

  const {
    requestOtp,
    verifyOtp,
    continueAsGuest,
    completeProfile,
  } = useAuth();

  const navigate = useNavigate();
  const location = useLocation();

  const dest = location.state?.from?.pathname || "/";

  const [step, setStep] = useState("mode");
  const [authMode, setAuthMode] = useState(null);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [demoOtp, setDemoOtp] = useState("");

  const [profile, setProfile] = useState({
    name: "",
    location: "",
    crop: "",
    cropOther: "",
  });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [accountNotFound, setAccountNotFound] = useState(false);

  const chooseLogin = () => {
    setAuthMode("login");
    setError("");
    setAccountNotFound(false);
    setStep("phone");
  };

  const chooseSignup = () => {
    setAuthMode("signup");
    setError("");
    setAccountNotFound(false);
    setStep("signupName");
  };

  const goToSignup = () => {
    setAuthMode("signup");
    setError("");
    setAccountNotFound(false);
    setStep("signupName");
  };

  const handlePhoneChange = (e) => {
    setPhone(e.target.value);
    if (error || accountNotFound) {
      setError("");
      setAccountNotFound(false);
    }
  };

  const submitSignupName = (e) => {
    e.preventDefault();
    setStep("phone");
  };

  const sendOtp = async (e) => {
    e.preventDefault();

    if (!isValidPhone(phone)) {
      setAccountNotFound(false);
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }

    setBusy(true);
    setError("");
    setAccountNotFound(false);

    try {
      const resp = await requestOtp(phone, authMode);

      setDemoOtp(resp.demo_otp || "");
      setOtp("");
      setStep("otp");
    } catch (err) {
      if (err?.status === 404 || err?.detail?.includes("No account found")) {
        setAccountNotFound(true);
        setError("No account found with this mobile number. Please sign up first.");
      } else {
        setAccountNotFound(false);
        setError(formatAuthError(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e) => {
    e.preventDefault();

    setBusy(true);
    setError("");

    try {
      const resp = await verifyOtp(phone, otp, authMode);

      console.log("🔥 OTP VERIFY RESPONSE:", resp);

      if (resp.is_new) {
        setStep("profile");
      } else {
        navigate(dest, { replace: true });
      }
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const guest = async () => {
    setBusy(true);
    setError("");

    try {
      await continueAsGuest();
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  const finishProfile = async (e) => {
    e.preventDefault();

    console.log("🔥 FINISH PROFILE CLICKED");

    setBusy(true);
    setError("");

    try {
      const crop =
        profile.crop === t("login.cropOther")
          ? profile.cropOther
          : profile.crop;

      console.log("PROFILE BEFORE SUBMIT:", profile);

      const updated = await completeProfile({
        name: profile.name,
        location_label: profile.location,
        primary_crop: crop,
      });

      console.log("PROFILE AFTER SUBMIT:", updated);

      navigate(dest, { replace: true });
    } catch (err) {
      console.error("PROFILE UPDATE ERROR:", err);
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-stretch justify-center bg-canvas px-0 py-0 md:px-6 md:py-10">
      <div className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-full bg-surface/90 p-1 shadow-sm backdrop-blur md:right-6 md:top-6">
        <ThemeToggle />
        <LanguageSwitcher />
      </div>

      <div className="flex w-full max-w-4xl flex-col overflow-hidden bg-surface shadow-sm md:flex-row md:rounded-3xl md:border md:border-line">
        <Hero />

        <div className="flex flex-1 flex-col justify-center px-6 py-10 sm:px-10">
          <div className="mx-auto w-full max-w-sm">
            <div className="mb-6 flex items-center gap-2.5 md:hidden">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-700 text-white">
                <Icon name="sprout" className="h-4.5 w-4.5" />
              </span>

              <span className="text-base font-bold tracking-tight text-ink">
                AgriSmart
              </span>
            </div>

            {step === "mode" && (
              <ModeStep
                t={t}
                busy={busy}
                onChooseLogin={chooseLogin}
                onChooseSignup={chooseSignup}
                onGuest={guest}
              />
            )}

            {step === "signupName" && (
              <SignupNameStep
                t={t}
                name={profile.name}
                setName={(name) =>
                  setProfile((f) => ({ ...f, name }))
                }
                busy={busy}
                onSubmit={submitSignupName}
                onBack={() => {
                  setStep("mode");
                  setError("");
                }}
              />
            )}

            {step === "phone" && (
              <PhoneStep
                t={t}
                phone={phone}
                setPhone={handlePhoneChange}
                busy={busy}
                error={error}
                accountNotFound={accountNotFound}
                onGoToSignup={goToSignup}
                onSend={sendOtp}
                onBack={() => {
                  setStep(
                    authMode === "signup"
                      ? "signupName"
                      : "mode"
                  );
                  setError("");
                  setAccountNotFound(false);
                }}
              />
            )}

            {step === "otp" && (
              <OtpStep
                t={t}
                phone={phone}
                demoOtp={demoOtp}
                otp={otp}
                setOtp={setOtp}
                busy={busy}
                error={error}
                onVerify={verify}
                onChangeNumber={() => {
                  setStep("phone");
                  setError("");
                }}
                onResend={sendOtp}
              />
            )}

            {step === "profile" && (
              <ProfileStep
                t={t}
                form={profile}
                setForm={setProfile}
                busy={busy}
                error={error}
                onSubmit={finishProfile}
                skipName={
                  authMode === "signup" &&
                  !!profile.name.trim()
                }
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}