"""Module E extra — local speech-to-text for the assistant's mic button.

Runs entirely on this server via faster-whisper (CTranslate2 + a Whisper
model) — the browser only ever talks to this backend, never a cloud speech
API, so voice input keeps working with no internet access at all beyond
that. ``faster_whisper`` is imported lazily inside ``_model()`` so nothing
elsewhere pays for loading it (mirrors ``model/infer.py``'s lazy torch
import for the disease-scan model).
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from functools import lru_cache
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)

# Whisper's language codes happen to match ours for all seven.
_SUPPORTED = {"en", "hi", "gu", "mr", "ta", "te", "pa"}

# Unicode letter blocks for the Indic languages we force Whisper into. Even
# with language="gu"/"hi"/etc. forced, a weak/uncertain model can still
# hallucinate a transcript in an unrelated script (seen in practice as
# Perso-Arabic-looking output for Gujarati) — that garbled text is worse than
# no text, since it gets shown as the user's own message and forwarded to the
# LLM as their question. Marathi shares Devanagari with Hindi, so a wrong-script
# check can't tell them apart — that's fine, both are legitimate here.
_SCRIPT_RANGES = {
    "gu": (0x0A80, 0x0AFF),  # Gujarati
    "hi": (0x0900, 0x097F),  # Devanagari
    "mr": (0x0900, 0x097F),  # Devanagari (shared with Hindi)
    "ta": (0x0B80, 0x0BFF),  # Tamil
    "te": (0x0C00, 0x0C7F),  # Telugu
    "pa": (0x0A00, 0x0A7F),  # Gurmukhi
}


def _looks_like_wrong_script(text: str, lang: str) -> bool:
    """True if ``text`` is dominated by an unrelated non-Indian, non-Latin
    script (e.g. Perso-Arabic, Cyrillic, CJK) that Whisper occasionally
    hallucinates during background noise or silence."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    # Check if letters are dominated by foreign hallucinated scripts (Arabic, Cyrillic, CJK, Thai)
    foreign = sum(
        1
        for c in letters
        if (
            0x0600 <= ord(c) <= 0x06FF  # Arabic / Perso-Arabic
            or 0x0400 <= ord(c) <= 0x04FF  # Cyrillic
            or 0x4E00 <= ord(c) <= 0x9FFF  # CJK
            or 0x0E00 <= ord(c) <= 0x0E7F  # Thai
        )
    )
    return (foreign / len(letters)) > 0.4


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
            text = ""
        if not text:
            # If nothing was recognized under forced language, attempt auto-detect
            try:
                segments_auto, _info_auto = model.transcribe(path, vad_filter=True)
                candidate = " ".join(seg.text.strip() for seg in segments_auto).strip()
                if candidate and not _looks_like_wrong_script(candidate, _info_auto.language):
                    text = candidate
            except Exception as auto_exc:
                log.debug("Auto-detect transcribe fallback error: %s", auto_exc)
        return text
    finally:
        Path(path).unlink(missing_ok=True)


async def warm_up() -> None:
    """Loads the Whisper model at server startup instead of on whoever's
    first recording — profiled at 100+ seconds on a machine with no local
    model cache yet (a real download, not just a load-into-memory), which
    is exactly the kind of wait the mic button shouldn't ever produce for
    a real user. Best-effort: a failure here just means the first real
    recording pays the load cost instead, same as before this existed."""
    try:
        await asyncio.to_thread(_model)
    except Exception as exc:
        log.warning("Whisper warm-up skipped (voice input will still work, just slower on the first use): %s", exc)
