"""Module E extra — local speech-to-text for the assistant's mic button.

Runs entirely on this server via faster-whisper (CTranslate2 + a Whisper
model) — the browser only ever talks to this backend, never a cloud speech
API, so voice input keeps working with no internet access at all beyond
that. ``faster_whisper`` is imported lazily inside ``_model()`` so nothing
elsewhere pays for loading it (mirrors ``model/infer.py``'s lazy torch
import for the disease-scan model).
"""

from __future__ import annotations

import logging
import tempfile
from functools import lru_cache
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)

# Whisper's language codes happen to match ours for en/hi/gu.
_SUPPORTED = {"en", "hi", "gu"}

# Unicode letter blocks for the Indic languages we force Whisper into. Even
# with language="gu"/"hi" forced, a weak/uncertain model can still hallucinate
# a transcript in an unrelated script (seen in practice as Perso-Arabic-looking
# output for Gujarati) — that garbled text is worse than no text, since it gets
# shown as the user's own message and forwarded to the LLM as their question.
_SCRIPT_RANGES = {
    "gu": (0x0A80, 0x0AFF),  # Gujarati
    "hi": (0x0900, 0x097F),  # Devanagari
}


def _looks_like_wrong_script(text: str, lang: str) -> bool:
    """True if ``text`` is dominated by a script other than the one expected
    for ``lang`` — a sign Whisper mis-transcribed into an unrelated language
    rather than genuinely hearing that script."""
    lo, hi = _SCRIPT_RANGES.get(lang, (None, None))
    if lo is None:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    in_script = sum(1 for c in letters if lo <= ord(c) <= hi)
    return in_script / len(letters) < 0.5


@lru_cache
def _model():
    from faster_whisper import WhisperModel

    s = get_settings()
    log.info("Loading Whisper model %s (first call only)...", s.whisper_model_size)
    return WhisperModel(s.whisper_model_size, device="cpu", compute_type=s.whisper_compute_type)


def transcribe(audio_bytes: bytes, suffix: str, lang: str = "en") -> str:
    """Transcribe a short recorded clip. ``suffix`` should include the dot
    (e.g. ".webm") — faster-whisper decodes via ffmpeg's libraries (bundled
    with its ``av`` dependency), so most browser recording formats work."""
    model = _model()
    with tempfile.NamedTemporaryFile(suffix=suffix or ".webm", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        segments, _info = model.transcribe(
            path,
            language=lang if lang in _SUPPORTED else None,
            vad_filter=True,  # trims leading/trailing silence
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if _looks_like_wrong_script(text, lang):
            # Whisper hallucinated an unrelated script rather than genuinely
            # hearing one — treat it the same as "no speech detected" instead
            # of handing garbled text to the user and the LLM as their question.
            log.warning("Discarding transcript in unexpected script for lang=%s", lang)
            return ""
        return text
    finally:
        Path(path).unlink(missing_ok=True)
