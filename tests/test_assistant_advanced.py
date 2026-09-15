"""Tests for Advanced Conversational AI Farm Assistant:
- Multi-turn conversation awareness & anaphora resolution
- Deep plot telemetry fusion (active planting, diagnosis, weather forecast)
- Contextual suggested follow-ups (multilingual)
- Deep-link action shortcuts (/scan, /weather, /soil, /plots/{id})
- Organic concoctions & Government agricultural schemes FAQs
"""

import pytest

from app.backend.models.modules import ChatMessage
from app.backend.services.assistant import (
    answer_question,
    _resolve_context_query,
    _generate_followups,
    _generate_shortcuts,
)


def test_resolve_context_query_anaphora():
    history = [
        ChatMessage(role="user", content="Tell me about tomato late blight"),
        ChatMessage(role="assistant", content="Tomato Late Blight is caused by Phytophthora infestans."),
    ]
    # Follow-up with no crop or disease explicitly mentioned
    resolved = _resolve_context_query("What is the chemical dose and waiting period?", history)
    assert "tomato late blight" in resolved.lower() or "late blight" in resolved.lower()


def test_resolve_context_query_standalone():
    history = [
        ChatMessage(role="user", content="Tell me about tomato late blight"),
        ChatMessage(role="assistant", content="Tomato Late Blight is caused by Phytophthora infestans."),
    ]
    # Standalone query about a completely different crop/disease shouldn't be polluted
    resolved = _resolve_context_query("How to treat wheat rust in Punjab?", history)
    assert "wheat rust" in resolved.lower()
    assert "tomato" not in resolved.lower()


@pytest.mark.asyncio
async def test_assistant_multi_turn_anaphora():
    # Turn 1: user asks about tomato late blight
    turn1_history = []
    ans1 = await answer_question(
        "Tell me about tomato late blight",
        lang="en",
        history=turn1_history,
    )
    assert "metalaxyl" in ans1.answer.lower() or "late blight" in ans1.answer.lower()
    assert ans1.suggested_followups
    assert ans1.action_shortcuts

    # Turn 2: user asks follow-up "What chemical spray or treatment should I use for it?"
    turn2_history = [
        ChatMessage(role="user", content="Tell me about tomato late blight"),
        ChatMessage(role="assistant", content=ans1.answer),
    ]
    ans2 = await answer_question(
        "What chemical spray or treatment should I use for it?",
        lang="en",
        history=turn2_history,
    )
    # Should resolve late blight context and provide chemical treatment
    assert "mancozeb" in ans2.answer.lower() or "chemical control" in ans2.answer.lower()
    assert any("tomato" in g.lower() or "late_blight" in g.lower() for g in ans2.grounded_on)


@pytest.mark.asyncio
async def test_assistant_action_shortcuts_generation():
    # Query with disease/symptom keywords should produce /scan shortcut
    ans_disease = await answer_question("My leaves have yellow spots and blight", lang="en")
    routes = [s.route for s in ans_disease.action_shortcuts]
    assert "/scan" in routes

    # Query with weather/spray keywords should produce /weather shortcut
    ans_weather = await answer_question("Can I spray pesticide tomorrow?", lang="en")
    routes_w = [s.route for s in ans_weather.action_shortcuts]
    assert "/weather" in routes_w

    # Query with soil/fertilizer keywords should produce /soil shortcut
    ans_soil = await answer_question("What fertilizer should I use for acidic soil?", lang="en")
    routes_s = [s.route for s in ans_soil.action_shortcuts]
    assert "/soil" in routes_s

    # When a plot is provided, should include link to plot detail
    plot = {"id": "plot-xyz-123", "name": "East Block", "main_crop": "Cotton"}
    ans_plot = await answer_question("How is my plot doing?", lang="en", plot=plot)
    routes_p = [s.route for s in ans_plot.action_shortcuts]
    assert "/plots/plot-xyz-123" in routes_p


@pytest.mark.asyncio
async def test_assistant_suggested_followups_multilingual():
    # English follow-ups
    ans_en = await answer_question("Tell me about tomato early blight", lang="en")
    assert len(ans_en.suggested_followups) >= 2
    assert any("chemical" in f.lower() or "waiting" in f.lower() or "spray" in f.lower() for f in ans_en.suggested_followups)

    # Hindi follow-ups
    ans_hi = await answer_question("टमाटर अगेती झुलसा का इलाज बताएं", lang="hi")
    assert len(ans_hi.suggested_followups) >= 2
    assert any("दवा" in f or "छिड़काव" in f or "जैविक" in f for f in ans_hi.suggested_followups)

    # Gujarati follow-ups
    ans_gu = await answer_question("ટામેટા આગોતરો સુકારો વિશે જણાવો", lang="gu")
    assert len(ans_gu.suggested_followups) >= 2
    assert any("દવા" in f or "છંટકાવ" in f or "જૈવિક" in f for f in ans_gu.suggested_followups)


@pytest.mark.asyncio
async def test_assistant_concoctions_faq():
    # Jeevamrut
    ans_jeevamrut = await answer_question("How do I make Jeevamrut bio-fertilizer?", lang="en")
    assert "cow dung" in ans_jeevamrut.answer.lower() or "jaggery" in ans_jeevamrut.answer.lower()
    assert "faq:concoctions" in ans_jeevamrut.grounded_on

    # Neem oil spray
    ans_neem = await answer_question("What is the dilution for neem oil spray?", lang="en")
    assert "5 ml" in ans_neem.answer.lower() or "neem" in ans_neem.answer.lower()
    assert "faq:concoctions" in ans_neem.grounded_on


@pytest.mark.asyncio
async def test_assistant_schemes_faq():
    # PM-KISAN
    ans_kisan = await answer_question("What is the PM-KISAN government scheme?", lang="en")
    assert "6,000" in ans_kisan.answer or "installment" in ans_kisan.answer.lower()
    assert "faq:schemes" in ans_kisan.grounded_on

    # Crop Insurance / PMFBY
    ans_pmfby = await answer_question("Tell me about PMFBY crop insurance", lang="en")
    assert "pmfby" in ans_pmfby.answer.lower() or "insurance" in ans_pmfby.answer.lower()
    assert "faq:schemes" in ans_pmfby.grounded_on


@pytest.mark.asyncio
async def test_assistant_plot_telemetry_fusion():
    # Comprehensive plot telemetry passed to assistant
    plot = {
        "id": "p-99",
        "name": "South Orchard",
        "main_crop": "Tomato",
        "active_planting": {
            "crop": "Tomato",
            "stage": "Flowering & Fruit Set",
            "sown_date": "2026-07-01",
        },
        "latest_diagnosis": {
            "disease": "Tomato Early Blight",
            "confidence": 0.94,
        },
        "weather_summary": {
            "rain_prob": 75,
            "rain_mm": 12.0,
            "tmax": 31,
            "wind": 14,
        },
    }

    ans = await answer_question("What should I be careful of on this plot right now?", lang="en", plot=plot)
    assert "tomato" in ans.answer.lower()
    assert "flowering" in ans.answer.lower() or "early blight" in ans.answer.lower() or "rain" in ans.answer.lower()
    assert "plot:crop" in ans.grounded_on
