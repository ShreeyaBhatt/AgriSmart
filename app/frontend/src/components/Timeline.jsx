import Icon from "./Icon.jsx";

const ICON = { diagnosis: "camera", irrigation: "droplet", action: "leaf" };

export default function Timeline({ entries }) {
  if (!entries?.length) {
    return <p className="text-xs text-faint">No activity yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {entries.map((e) => (
        <li key={`${e.kind}-${e.ref_id}`} className="flex gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <Icon name={ICON[e.kind] || "spark"} className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0 flex-1 border-b border-line pb-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-sm font-medium text-ink">{e.title}</span>
              <span className="shrink-0 text-[11px] text-faint">
                {new Date(e.at).toLocaleDateString()}
              </span>
            </div>
            {e.detail && <p className="text-xs text-muted">{e.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
