from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import create_app
from app.services.ai_chat import build_farmer_context, chat_with_farmer


class FakeClient:
    class Responses:
        @staticmethod
        def create(**kwargs):
            FakeClient.last_request = kwargs
            return SimpleNamespace(output_text="Use Book Slot to request a mandi visit.")

    responses = Responses()

    class Chat:
        class Completions:
            @staticmethod
            def create(**kwargs):
                FakeClient.last_request = kwargs
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="Use Book Slot to request a mandi visit."))]
                )

        completions = Completions()

    chat = Chat()


def test_chat_service_returns_model_reply_without_exposing_configuration():
    app = create_app()
    app.config["OPENAI_API_KEY"] = "test-key"
    app.config["AI_PROVIDER"] = "openai"
    with app.app_context(), patch("app.services.ai_chat._openai_client", return_value=FakeClient()):
        reply = chat_with_farmer(
            "How do I book a slot?",
            [{"role": "user", "content": "Hello"}],
            language="kn",
        )

    assert reply == "Use Book Slot to request a mandi visit."
    assert FakeClient.last_request["instructions"].startswith("You are KisanQueue")
    assert "Kannada" in FakeClient.last_request["instructions"]
    assert FakeClient.last_request["input"][-1]["content"] == "How do I book a slot?"


def test_chat_service_reports_missing_key():
    app = create_app()
    app.config["OPENAI_API_KEY"] = None
    app.config["AI_PROVIDER"] = "openai"
    with app.app_context(), patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            chat_with_farmer("Hello", [])


def test_farmer_context_reads_today_slot_availability_from_database():
    app = create_app()
    with app.app_context():
        context = build_farmer_context("What slots are available today?", 1)

    assert "Database date:" in context
    assert "Available slots today:" in context or "No available slots" in context
