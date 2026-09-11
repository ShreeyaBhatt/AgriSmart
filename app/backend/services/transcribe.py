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
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        Path(path).unlink(missing_ok=True)
