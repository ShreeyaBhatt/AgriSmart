import { useRef } from "react";

/** `length` separate digit boxes. `value`/`onChange` work with a plain string. */
export default function OtpInput({ length = 6, value, onChange, autoFocus = true }) {
  const refs = useRef([]);
  const digits = Array.from({ length }, (_, i) => value[i] || "");

  const setDigit = (i, d) => {
    const next = digits.slice();
    next[i] = d;
    onChange(next.join(""));
  };

  const handleChange = (i) => (e) => {
    const raw = e.target.value.replace(/\D/g, "");
    if (!raw) {
      setDigit(i, "");
      return;
    }
    // Typing (or autofill) can land more than one digit in a box — spread it forward.
    const chars = raw.split("");
    const next = digits.slice();
    let cursor = i;
    for (const ch of chars) {
      if (cursor >= length) break;
      next[cursor] = ch;
      cursor += 1;
    }
    onChange(next.join(""));
    refs.current[Math.min(cursor, length - 1)]?.focus();
  };

  const handleKeyDown = (i) => (e) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
    if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus();
    if (e.key === "ArrowRight" && i < length - 1) refs.current[i + 1]?.focus();
  };

  const handlePaste = (e) => {
    const raw = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!raw) return;
    e.preventDefault();
    onChange(raw.padEnd(digits.length, "").slice(0, length));
    refs.current[Math.min(raw.length, length - 1)]?.focus();
  };

  return (
    <div className="flex justify-center gap-2" onPaste={handlePaste}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          value={d}
          onChange={handleChange(i)}
          onKeyDown={handleKeyDown(i)}
          autoFocus={autoFocus && i === 0}
          inputMode="numeric"
          maxLength={length} // allow a full paste to land in any box; handleChange trims it
          className="h-12 w-11 rounded-xl border border-line bg-canvas/60 text-center text-lg font-semibold text-ink outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-300/40"
          aria-label={`Digit ${i + 1}`}
        />
      ))}
    </div>
  );
}
