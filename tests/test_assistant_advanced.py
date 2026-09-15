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


@pytest.mark.asyncio
async def test_assistant_multilingual_disease_fallback():
    # Test Hindi disease query produces Hindi crop, disease, and precautions
    ans_hi = await answer_question("टमाटर पछेती झुलसा", lang="hi")
    assert "टमाटर" in ans_hi.answer
    assert "झुलसा" in ans_hi.answer
    assert ans_hi.action_shortcuts[0].label == "पत्ती रोग स्कैन"

    # Test Gujarati disease query produces Gujarati shortcuts
    ans_gu = await answer_question("ટામેટા પાછોતરો સુકારો", lang="gu")
    assert "પાંદડા રોગ સ્કેન" in [s.label for s in ans_gu.action_shortcuts]

    # Test Marathi disease query produces Marathi crop and precautions
    ans_mr = await answer_question("टोमॅटो करपा रोग", lang="mr")
    assert "टोमॅटो" in ans_mr.answer
    assert "पानांचे रोग स्कॅन" in [s.label for s in ans_mr.action_shortcuts]


@pytest.mark.asyncio
async def test_assistant_tts_generation():
    from app.backend.services.assistant import (
        _TTS_CACHE,
        _clean_text_for_speech,
        generate_tts_audio,
        prewarm_tts,
        stream_tts_audio,
    )

    # Generates valid audio bytes in Hindi
    hi_audio = generate_tts_audio("नमस्ते किसान भाई, एग्रीस्मार्ट में आपका स्वागत है", lang="hi")
    assert len(hi_audio) > 1000
    assert hi_audio.startswith(b"\xff\xfb") or b"ID3" in hi_audio[:10] or len(hi_audio) > 5000

    # Generates valid audio in English with cache hit
    en_audio1 = generate_tts_audio("Welcome to AgriSmart", lang="en")
    en_audio2 = generate_tts_audio("Welcome to AgriSmart", lang="en")
    assert en_audio1 == en_audio2

    # Verify speech cleaner produces concise, natural spoken text
    long_raw = "Tomato — Early Blight. 1. Copper oxychloride @ 2.5 g/L. 2. Remove leaves. Avoid overhead irrigation."
    cleaned = _clean_text_for_speech(long_raw)
    assert "2.5 g/L" in cleaned
    assert len(cleaned) <= 240

    # Verify stream_tts_audio yields chunks and populates cache
    chunks = list(stream_tts_audio("Testing streaming TTS latency.", lang="en"))
    assert len(chunks) >= 1
    assert sum(len(c) for c in chunks) > 500


@pytest.mark.asyncio
async def test_assistant_answer_speech_text_populated():
    ans = await answer_question("What is tomato early blight?", lang="en")
    assert ans.speech_text is not None
    assert len(ans.speech_text) <= 240
    assert "early blight" in ans.speech_text.lower()


@pytest.mark.asyncio
async def test_assistant_multilingual_inflection_retrieval():
    from app.backend.services.assistant import _retrieve

    # Gujarati with inflectional suffix -માં
    gu_picks = _retrieve("ટામેટામાં આગોતરો સુકારો કેવી રીતે મટે?", None)
    assert len(gu_picks) > 0
    assert "Tomato" in gu_picks[0][0]

    # Tamil with inflectional suffix
    ta_picks = _retrieve("தக்காளியில் இலை கருகல் நோய்", None)
    assert len(ta_picks) > 0
    assert "Tomato" in ta_picks[0][0]

    # Telugu with inflectional suffix
    te_picks = _retrieve("టమోటాలో ముందస్తు తెగులు", None)
    assert len(te_picks) > 0
    assert "Tomato" in te_picks[0][0]

    # Punjabi with inflectional suffix
    pa_picks = _retrieve("ਟਮਾਟਰਾਂ ਵਿੱਚ ਝੁਲਸ ਰੋਗ", None)
    assert len(pa_picks) > 0
    assert "Tomato" in pa_picks[0][0]


def test_transcribe_script_filter():
    from app.backend.services.transcribe import _looks_like_wrong_script

    # Indic scripts and Latin words must NEVER be discarded
    assert not _looks_like_wrong_script("टमाटर में रोग", "hi")
    assert not _looks_like_wrong_script("ટામેટામાં આગોતરો સુકારો", "gu")
    assert not _looks_like_wrong_script("tamatar early blight spray", "hi")
    assert not _looks_like_wrong_script("தக்காளி கருகல்", "ta")
    assert not _looks_like_wrong_script("టమోటా తెగులు", "te")
    assert not _looks_like_wrong_script("ਟਮਾਟਰ ਝੁਲਸ", "pa")

    # Unrelated foreign script hallucinated during silence must be flagged
    assert _looks_like_wrong_script("مرحبا بكم في هذا الصباح", "hi")


@pytest.mark.asyncio
async def test_assistant_multilingual_context_resolution():
    from app.backend.services.assistant import _resolve_context_query

    # Hindi follow-up with pronoun "इसकी"
    hi_history = [{"role": "user", "text": "टमाटर में अगेती झुलसा"}, {"role": "assistant", "text": "यह एक फफूंद रोग है।"}]
    res_hi = _resolve_context_query("इसकी रोकथाम की दवा क्या है?", hi_history)
    assert "टमाटर" in res_hi or "tomato" in res_hi or "झुलसा" in res_hi

    # Gujarati follow-up with pronoun "આની"
    gu_history = [{"role": "user", "text": "ટામેટામાં સુકારો"}, {"role": "assistant", "text": "આ ફૂગજન્ય રોગ છે."}]
    res_gu = _resolve_context_query("આની દવા જણાવો", gu_history)
    assert "ટામેટા" in res_gu or "tomato" in res_gu or "સૂકારો" in res_gu


@pytest.mark.asyncio
async def test_assistant_operational_query_with_prior_diagnosis_runs_agent(monkeypatch):
    """When a plot has an active fungal scan (e.g. Grape Black rot), asking an operational
    question like 'Should I irrigate today?' must trigger the Autonomous Agent (Module G)
    rather than vomiting the static leaf disease diagnosis card."""
    from app.backend.services import weather as weather_service

    async def fake_forecast(lat, lon):
        return {
            "hourly": {
                "relative_humidity_2m": [85] * 24,
                "precipitation": [0.5] * 24,
            },
            "daily": {
                "precipitation_probability_max": [80, 70, 60],
                "precipitation_sum": [12.0, 5.0, 0.0],
                "temperature_2m_max": [29, 28, 27],
                "temperature_2m_min": [19, 18, 18],
                "wind_speed_10m_max": [15, 12, 10],
            },
        }

    monkeypatch.setattr(weather_service, "fetch_forecast", fake_forecast)

    plot = {
        "id": "plot-vineyard",
        "name": "North Vineyard",
        "lat": 20.0,
        "lon": 74.0,
        "main_crop": "Grape",
        "planting": {"crop": "Grape", "stage": "Fruiting"},
        "soil_snapshot": {"ph": 6.5, "texture_class": "Loam"},
        "latest_diagnosis": {"predicted_class": "Grape___Black_rot", "abstained": False},
    }

    ans = await answer_question(
        "Should I irrigate today?",
        lang="en",
        plot=plot,
        last_class="Grape___Black_rot",
    )

    # Must NOT be the raw disease signs card
    assert "tan leaf spots with dark pycnidia dots" not in ans.answer.lower()

    # Must be the Autonomous Agent directive
    assert "autonomous farm agent directive" in ans.answer.lower()
    assert "halt irrigation" in ans.answer.lower() or "delay irrigation" in ans.answer.lower()
    assert "agent decision trace" in ans.answer.lower()
    assert "tier1-rule-401" in ans.answer.lower()
    assert "weather" in ans.grounded_on
    assert "agent" in ans.grounded_on


@pytest.mark.asyncio
async def test_assistant_disease_treatment_query_returns_treatment_card():
    """Asking specifically about disease treatment or cure should retrieve the treatment card."""
    ans = await answer_question(
        "How do I treat black rot on grape?",
        lang="en",
        last_class="Grape___Black_rot",
    )
    assert "grape" in ans.answer.lower()
    assert "black rot" in ans.answer.lower()
    assert "organic" in ans.answer.lower()
    assert "chemical" in ans.answer.lower()


@pytest.mark.asyncio
async def test_assistant_agent_intent_query_triggers_react_loop(monkeypatch):
    """Asking 'What should I do on my farm today?' triggers Autonomous Agent advisory."""
    from app.backend.services import weather as weather_service

    async def fake_forecast(lat, lon):
        return {
            "hourly": {"relative_humidity_2m": [50] * 24, "precipitation": [0.0] * 24},
            "daily": {
                "precipitation_probability_max": [10],
                "precipitation_sum": [0.0],
                "temperature_2m_max": [28],
                "temperature_2m_min": [18],
                "wind_speed_10m_max": [8],
            },
        }

    monkeypatch.setattr(weather_service, "fetch_forecast", fake_forecast)

    plot = {
        "id": "p-1",
        "name": "East Block",
        "lat": 23.0,
        "lon": 72.5,
        "main_crop": "Wheat",
        "planting": {"crop": "Wheat", "stage": "Tillering"},
        "soil_snapshot": None,
    }

    ans = await answer_question("What should I do on my farm today?", lang="en", plot=plot)
    assert "autonomous farm agent" in ans.answer.lower()
    assert "agent decision trace" in ans.answer.lower()
    assert "weather" in ans.grounded_on
    assert "agent" in ans.grounded_on


@pytest.mark.asyncio
async def test_assistant_spray_timing_query_runs_agent_and_not_disease_card(monkeypatch):
    """Asking 'So what about pesticides should i spray today or tomorrow?' with a plot having
    Tomato Bacterial spot must NOT return the static Tomato - Bacterial spot card, but rather
    the Autonomous Agent / Spray Weather directive."""
    from app.backend.services import weather as weather_service

    async def fake_forecast(lat, lon):
        return {
            "daily": {
                "precipitation_probability_max": [86, 70, 40],
                "precipitation_sum": [6.3, 2.0, 0.0],
                "temperature_2m_max": [30.4, 29.0, 28.0],
                "temperature_2m_min": [20.0, 19.0, 19.0],
                "wind_speed_10m_max": [13.5, 12.0, 10.0],
            },
            "hourly": {
                "precipitation": [0.3] * 24,
                "relative_humidity_2m": [78] * 24,
            },
        }

    monkeypatch.setattr(weather_service, "fetch_forecast", fake_forecast)

    plot = {
        "id": "plot-odhav",
        "name": "Odhav",
        "lat": 23.04573,
        "lon": 72.56474,
        "main_crop": "Tomato",
        "planting": {"crop": "Tomato", "stage": "Vegetative"},
        "soil_snapshot": None,
        "latest_diagnosis": {"predicted_class": "Tomato___Bacterial_spot", "abstained": False},
    }

    ans = await answer_question(
        "So what about pesticides should i spray today or tomorrow?",
        lang="en",
        plot=plot,
        last_class="Tomato___Bacterial_spot",
    )

    # Must NOT output the raw symptoms card
    assert "numerous small dark greasy spots on leaves" not in ans.answer.lower()

    # Must output the Autonomous Agent directive
    assert "autonomous farm agent directive" in ans.answer.lower()
    assert "agent decision trace" in ans.answer.lower()
    assert "weather" in ans.grounded_on
    assert "agent" in ans.grounded_on


@pytest.mark.asyncio
async def test_assistant_distinct_aspects_pesticides_and_waiting_period():
    """Verify that 'What pesticides should i use?' and 'What is the safety waiting period before harvest?'
    produce completely distinct, aspect-specific responses instead of repeating the identical disease card.
    """
    plot = {
        "id": "plot-odhav",
        "name": "Odhav",
        "lat": 23.04573,
        "lon": 72.56474,
        "main_crop": "Tomato",
        "planting": {"crop": "Tomato", "stage": "Fruiting"},
        "latest_diagnosis": {"predicted_class": "Tomato___Bacterial_spot", "abstained": False},
    }

    # Tile 1: "What pesticides should i use?"
    ans1 = await answer_question(
        "What pesticides should i use?",
        lang="en",
        plot=plot,
        last_class="Tomato___Bacterial_spot",
    )

    # Tile 2: "What is the safety waiting period before harvest?"
    history = [
        ChatMessage(role="user", content="What pesticides should i use?"),
        ChatMessage(role="assistant", content=ans1.answer),
    ]
    ans2 = await answer_question(
        "What is the safety waiting period before harvest?",
        lang="en",
        plot=plot,
        last_class="Tomato___Bacterial_spot",
        history=history,
    )

    # 1. Responses must NOT be identical
    assert ans1.answer != ans2.answer, "Responses for pesticides and waiting period must not be identical!"

    # 2. Tile 1 must focus on pesticides and application window, not symptoms or waiting period
    assert "Recommended Chemical & Pesticide Control" in ans1.answer
    assert "Application Window" in ans1.answer
    assert "Signs:" not in ans1.answer
    assert "Pre-Harvest Interval" not in ans1.answer

    # 3. Tile 2 must focus on safety waiting period and PHI, not symptoms or generic card
    assert "Safety Waiting Period (Pre-Harvest Interval)" in ans2.answer
    assert "7–10 days" in ans2.answer
    assert "3–5 days" in ans2.answer
    assert "Signs:" not in ans2.answer


