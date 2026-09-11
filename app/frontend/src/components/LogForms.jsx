import { useState } from "react";
import Icon from "./Icon.jsx";
import { api } from "../api.js";
import { useT } from "../i18n/useT.js";

const INPUT =
  "w-full rounded-lg border border-line bg-canvas/60 px-2.5 py-2 text-sm text-ink outline-none focus:border-brand-400";
const ACTION_TYPES = ["spray", "lime", "compost", "crop_change", "other"];

export default function LogForms({ plotId, onLogged }) {
  const t = useT();
  const [open, setOpen] = useState(null); // "irrigation" | "action" | null
  const [busy, setBusy] = useState(false);
  const [irr, setIrr] = useState({ amount_mm: "", method: "", note: "" });
  const [act, setAct] = useState({ action_type: "spray", details: "" });

  const submit = async (kind) => {
    setBusy(true);
    try {
      if (kind === "irrigation") {
        await api.logIrrigation({
          plot_id: plotId,
          amount_mm: irr.amount_mm ? Number(irr.amount_mm) : null,
          method: irr.method || null,
          note: irr.note || null,
        });
      } else {
        await api.logAction({ plot_id: plotId, action_type: act.action_type, details: act.details || null });
      }
      setOpen(null);
      setIrr({ amount_mm: "", method: "", note: "" });
      setAct({ action_type: "spray", details: "" });
      onLogged?.();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <button
          onClick={() => setOpen(open === "irrigation" ? null : "irrigation")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
        >
          <Icon name="droplet" className="h-3.5 w-3.5" /> {t("logs.irrigation")}
        </button>
        <button
          onClick={() => setOpen(open === "action" ? null : "action")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-canvas"
        >
          <Icon name="leaf" className="h-3.5 w-3.5" /> {t("logs.action")}
        </button>
      </div>

      {open === "irrigation" && (
        <div className="space-y-2 rounded-lg border border-line bg-canvas/40 p-3">
          <input className={INPUT} placeholder={t("logs.amount")} inputMode="decimal"
            value={irr.amount_mm} onChange={(e) => setIrr({ ...irr, amount_mm: e.target.value })} />
          <input className={INPUT} placeholder={t("logs.method")}
            value={irr.method} onChange={(e) => setIrr({ ...irr, method: e.target.value })} />
          <input className={INPUT} placeholder={t("logs.note")}
            value={irr.note} onChange={(e) => setIrr({ ...irr, note: e.target.value })} />
          <button disabled={busy} onClick={() => submit("irrigation")}
            className="w-full rounded-lg bg-brand-700 px-3 py-2 text-xs font-semibold text-white disabled:bg-line">
            {t("action.save")}
          </button>
        </div>
      )}

      {open === "action" && (
        <div className="space-y-2 rounded-lg border border-line bg-canvas/40 p-3">
          <select className={INPUT} value={act.action_type}
            onChange={(e) => setAct({ ...act, action_type: e.target.value })}>
            {ACTION_TYPES.map((a) => (
              <option key={a} value={a}>{t(`logs.type.${a}`)}</option>
            ))}
          </select>
          <input className={INPUT} placeholder={t("logs.details")}
            value={act.details} onChange={(e) => setAct({ ...act, details: e.target.value })} />
          <button disabled={busy} onClick={() => submit("action")}
            className="w-full rounded-lg bg-brand-700 px-3 py-2 text-xs font-semibold text-white disabled:bg-line">
            {t("action.save")}
          </button>
        </div>
      )}
    </div>
  );
}
