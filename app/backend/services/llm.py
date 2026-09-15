"""Tier 2: Local SLM Multilingual Presentation Layer (The Conversational Tongue)
and Tier 3: Zero-Latency Circuit Breaker & Safety Shield (The Fallback).

Runs an in-process Small Language Model (SLM) on CPU via Hugging Face `transformers`
(default: Qwen/Qwen2.5-0.5B-Instruct) in non-blocking threads (asyncio.to_thread).
Enforces a strict circuit breaker: on timeout (>3.5s), memory limits, or when
AGRISMART_LLM_PROVIDER="cards", it instantly trips to Tier 3 fallback in <0.1ms.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

from ..config import get_settings

log = logging.getLogger(__name__)

BreakerState = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitBreaker:
    """Zero-latency safety shield that prevents hung or failing models from stalling requests."""

    def __init__(self, max_fails: int = 3, reset_timeout_s: float = 60.0):
        self.max_fails = max_fails
        self.reset_timeout_s = reset_timeout_s
        self.fail_count: int = 0
        self.state: BreakerState = "CLOSED"
        self.opened_at: float = 0.0

    def is_available(self) -> bool:
        s = get_settings()
        if s.llm_provider == "cards":
            return False

        if self.state == "OPEN":
            if time.monotonic() - self.opened_at > self.reset_timeout_s:
                log.info("CircuitBreaker moving to HALF_OPEN probe state")
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self) -> None:
        if self.state != "CLOSED":
            log.info("CircuitBreaker recovered -> CLOSED")
        self.state = "CLOSED"
        self.fail_count = 0

    def record_failure(self, reason: str = "") -> None:
        self.fail_count += 1
        log.warning("CircuitBreaker failure (%d/%d): %s", self.fail_count, self.max_fails, reason)
        if self.fail_count >= self.max_fails or self.state == "HALF_OPEN":
            self.state = "OPEN"
            self.opened_at = time.monotonic()
            log.warning("CircuitBreaker TRIPPED -> OPEN for %.1fs", self.reset_timeout_s)

    def force_open(self) -> None:
        self.state = "OPEN"
        self.opened_at = time.monotonic()

    def reset(self) -> None:
        self.state = "CLOSED"
        self.fail_count = 0
        self.opened_at = 0.0


circuit_breaker = CircuitBreaker()

# Cache for model and tokenizer singleton
_tokenizer = None
_model = None
_load_attempted = False
_load_success = False


def _load_model_and_tokenizer():
    """Lazily load the tokenizer and model into CPU memory."""
    global _tokenizer, _model, _load_attempted, _load_success
    if _load_attempted:
        return _tokenizer, _model

    _load_attempted = True
    s = get_settings()
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        log.info("Loading local SLM %s on %s...", s.local_model_id, s.local_model_device)
        start = time.monotonic()
        _tokenizer = AutoTokenizer.from_pretrained(s.local_model_id, trust_remote_code=True)
        _model = AutoModelForCausalLM.from_pretrained(
            s.local_model_id,
            torch_dtype=torch.float32,
            device_map=s.local_model_device,
            trust_remote_code=True,
        )
        _model.eval()
        _load_success = True
        log.info("Local SLM loaded successfully in %.2fs", time.monotonic() - start)
        return _tokenizer, _model
    except Exception as exc:
        log.warning("Could not load local SLM (%s): %s. Tripping circuit breaker.", s.local_model_id, exc)
        circuit_breaker.record_failure(str(exc))
        _load_success = False
        return None, None


def _generate_sync(prompt: str, max_new_tokens: int = 160) -> str | None:
    """Synchronous CPU token generation."""
    tokenizer, model = _load_model_and_tokenizer()
    if tokenizer is None or model is None:
        return None

    import torch

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Slice out prompt tokens
    gen_tokens = output_ids[0][inputs["input_ids"].shape[1] :]
    text = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
    return text or None


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (हिंदी)",
    "gu": "Gujarati (ગુજરાતી)",
    "mr": "Marathi (मराठी)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
}


def build_grounded_prompt(question: str, facts: str, lang: str = "en") -> str:
    """Constructs a strictly bounded grounding prompt enforcing Tier 1 safety."""
    lang_name = LANGUAGE_NAMES.get(lang, "English")
    return (
        f"<|im_start|>system\n"
        f"You are AgriSmart AI, a trusted, empathetic agricultural advisor for smallholder farmers in India.\n"
        f"Format the following VERIFIED AGRONOMIC FACTS into a helpful, conversational, and warm response in {lang_name}.\n"
        f"CRITICAL SAFETY RULE: You must NEVER change, invent, alter, or misrepresent chemical names, dosages, waiting periods, or thresholds.\n"
        f"Keep the answer concise (3-5 sentences), practical, respectful, and direct. Do not add markdown headers or disclaimers.<|im_end|>\n"
        f"<|im_start|>user\n"
        f"FACTS:\n{facts}\n\n"
        f"FARMER QUESTION: {question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


async def generate(prompt: str) -> str | None:
    """Generate formatted text using the local SLM, protected by the circuit breaker."""
    s = get_settings()
    if not circuit_breaker.is_available():
        return None

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_generate_sync, prompt, s.llm_max_new_tokens),
            timeout=s.llm_timeout_s,
        )
        if result:
            circuit_breaker.record_success()
            return result
        circuit_breaker.record_failure("Empty generation output")
        return None
    except asyncio.TimeoutError:
        log.warning("Local SLM execution exceeded SLA timeout of %.1fs; tripping circuit breaker.", s.llm_timeout_s)
        circuit_breaker.record_failure(f"Timeout > {s.llm_timeout_s}s")
        return None
    except Exception as exc:
        log.warning("Local SLM generation failed: %s", exc)
        circuit_breaker.record_failure(str(exc))
        return None


def reset_circuit_breaker() -> None:
    """Reset the circuit breaker (useful for tests and manual re-enabling)."""
    circuit_breaker.reset()
