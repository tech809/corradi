import asyncio

from app.llm import application


def _project():
    return {
        "identifier": "CORRADI-2026-0042",
        "title": "Green Voices",
        "type": "YOUTH_EXCHANGE",
        "topic": "sostenibilidad y participación juvenil",
        "summary": "Intercambio para aprender a comunicar iniciativas ambientales.",
        "participant_profile": "Jóvenes con interés en el tema; no requiere experiencia previa.",
        "learning_outcomes": "Comunicación, trabajo en equipo y participación.",
    }


def test_application_prompt_forbids_inventing_experience():
    prompt = application.build_prompt(
        _project(),
        {"task": "motivation", "motivation": "Quiero aprender", "experience": ""},
    )
    assert "No inventes experiencias" in prompt
    assert "Green Voices" in prompt
    assert "Quiero aprender" in prompt


def test_fake_assistant_marks_missing_personal_facts():
    result = asyncio.run(application.assist(
        _project(),
        {"task": "motivation", "draft": "", "motivation": "", "experience": "", "strengths": "", "languages": ""},
    ))
    assert "[explica aquí" in result["draft"]
    assert result["tips"]
    assert "revísalo" in result["notice"].lower()


def test_fake_assistant_keeps_review_draft():
    result = asyncio.run(application.assist(
        _project(),
        {"task": "review", "draft": "Este es mi texto real.", "motivation": "", "experience": "", "strengths": "", "languages": ""},
    ))
    assert result["draft"] == "Este es mi texto real."
