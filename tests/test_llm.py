"""Tests for Tier 2 Local SLM, Tier 3 Circuit Breaker, and Conversational Router."""

import time
import pytest

from app.backend.services import llm as llm_service
from app.backend.services.assistant import answer_question


def test_circuit_breaker_behavior():
    breaker = llm_service.CircuitBreaker(max_fails=2, reset_timeout_s=1.0)
    assert breaker.state == "CLOSED"
    
    # Record failures up to threshold
    breaker.record_failure("timeout")
    assert breaker.state == "CLOSED"
    breaker.record_failure("OOM")
    assert breaker.state == "OPEN"
    assert not breaker.is_available()

    # Reset
    breaker.reset()
    assert breaker.state == "CLOSED"
    assert breaker.fail_count == 0


def test_grounded_prompt_enforces_safety():
    prompt = llm_service.build_grounded_prompt(
        question="How to cure late blight?",
        facts="Metalaxyl + Mancozeb @ 2.5 g/L. Waiting period 14 days.",
        lang="hi",
    )
    assert "CRITICAL SAFETY RULE" in prompt
    assert "Metalaxyl + Mancozeb @ 2.5 g/L" in prompt
    assert "Hindi" in prompt


@pytest.mark.asyncio
async def test_assistant_greeting_intent_multilingual():
    # English greeting
    ans_en = await answer_question("Hello, what can you do?", lang="en")
    assert "agrismart" in ans_en.answer.lower()
    assert "diagnose" in ans_en.answer.lower() or "assistant" in ans_en.answer.lower()
    assert "faq:greeting" in ans_en.grounded_on

    # Hindi greeting
    ans_hi = await answer_question("नमस्ते, आप क्या कर सकते हैं?", lang="hi")
    assert "एग्रीस्मार्ट" in ans_hi.answer or "सहायक" in ans_hi.answer
    assert "faq:greeting" in ans_hi.grounded_on

    # Gujarati greeting
    ans_gu = await answer_question("કેમ છો, મને મદદ કરો", lang="gu")
    assert "એગ્રીસ્માર્ટ" in ans_gu.answer or "સહાયક" in ans_gu.answer
    assert "faq:greeting" in ans_gu.grounded_on


@pytest.mark.asyncio
async def test_assistant_expanded_agronomy_intents():
    # Weeding intent
    ans_weed = await answer_question("How do I control weeds in my field?", lang="en")
    assert "weed" in ans_weed.answer.lower()
    assert "faq:weeding" in ans_weed.grounded_on

    # Organic / compost intent
    ans_org = await answer_question("How to prepare organic compost or fym manure?", lang="en")
    assert "organic" in ans_org.answer.lower() or "compost" in ans_org.answer.lower() or "manure" in ans_org.answer.lower()
    assert "faq:organic" in ans_org.grounded_on

    # Leaf yellowing intent
    ans_yellow = await answer_question("Why are my plant leaves turning yellow?", lang="en")
    assert "yellow" in ans_yellow.answer.lower() or "nitrogen" in ans_yellow.answer.lower()
    assert "faq:yellow_leaves" in ans_yellow.grounded_on


@pytest.mark.asyncio
async def test_assistant_plot_context_guidance():
    # When a plot has an active crop declared, general queries reference that crop
    plot = {
        "name": "North Field",
        "lat": 23.0,
        "lon": 72.5,
        "area_ha": 2.5,
        "main_crop": "Tomato",
        "soil_snapshot": None,
    }
    ans = await answer_question("How should I care for my crop this week?", lang="en", plot=plot)
    assert "tomato" in ans.answer.lower()
    assert "plot:crop" in ans.grounded_on
