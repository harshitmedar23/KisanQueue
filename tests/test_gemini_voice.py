from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import create_app
from app.services.gemini_service import ask_farmer_voice, query_gemini
from app.services.voice_assistant import synthesize_speech


class FakeGeminiClient:
    class Models:
        @staticmethod
        def generate_content(**kwargs):
            FakeGeminiClient.last_request = kwargs
            return SimpleNamespace(text="Use the Book Slot page to request a mandi visit.")

    models = Models()


def test_gemini_query_uses_configured_model_without_exposing_key():
    app = create_app()
    app.config["GEMINI_API_KEY"] = "test-key"
    app.config["GEMINI_MODEL"] = "gemini-2.5-flash"
    with app.app_context(), patch("app.services.gemini_service._client", return_value=FakeGeminiClient()):
        reply = ask_farmer_voice("How do I book a slot?", language="kn")

    assert reply == "Use the Book Slot page to request a mandi visit."
    assert FakeGeminiClient.last_request["model"] == "gemini-2.5-flash"
    assert "Kannada" in FakeGeminiClient.last_request["contents"]
    assert "test-key" not in FakeGeminiClient.last_request["contents"]


def test_gemini_query_requires_configuration():
    app = create_app()
    app.config["GEMINI_API_KEY"] = None
    with app.app_context():
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            query_gemini("Hello")


def test_voice_route_is_registered_and_tts_imports():
    app = create_app()
    assert any(rule.rule == "/farmer/voice-assistant" for rule in app.url_map.iter_rules())
    assert callable(synthesize_speech)
