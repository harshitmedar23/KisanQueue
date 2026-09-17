import os
from datetime import date as date_cls

import requests
from flask import current_app

from app.extensions import db
from app.models import Booking, Centre, MandiPrice, SlotConfig


SYSTEM_PROMPT = """You are KisanQueue's helpful farmer-support assistant.
Your purpose is to help farmers with any practical question connected to farming,
agriculture, crops, soil, seeds, fertilizer, irrigation, pests, harvesting, storage,
crop selling, mandi prices, MSP, procurement, slot booking, booking approval, queue
tokens, payments, transport, pickup status, receipts, and visiting a procurement
centre. You may also answer simple everyday questions when they help the farmer.

Answer briefly, clearly, and practically in the language used by the farmer. Use simple
words and step-by-step advice when useful. Ask a short clarifying question when the
crop, location, season, or problem is unclear. For pests, diseases, chemicals, or
health and safety topics, give cautious general guidance and recommend a local
agriculture officer or expert for serious cases. Do not invent live weather, mandi
prices, slot availability, queue position, government rules, or contact details. Say
when current information must be checked in the app or with the local mandi.

Do not claim to have changed a booking, approved a slot, assigned a driver, processed
a payment, or accessed private account data. Tell the farmer to use the app or contact
their mandi for those actions. Never ask for passwords, OTPs, API keys, or other
secrets. If a question is unrelated and cannot help the farmer, answer briefly and
offer to help with a farming or procurement question instead. If you do not know
something, say so instead of guessing.
"""

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}


def _openai_client():
    api_key = current_app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("AI assistant is not configured. Add OPENAI_API_KEY to the .env file.")
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def _ollama_reply(input_items):
    base_url = current_app.config.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = current_app.config.get("OLLAMA_MODEL", "llama3.2")
    timeout = current_app.config.get("OLLAMA_TIMEOUT_SECONDS", 120)
    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": input_items,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 220},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.ConnectionError as error:
        raise RuntimeError("Ollama is not running. Start Ollama and try again.") from error
    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond. Please try again.") from error
    except requests.RequestException as error:
        raise RuntimeError("The local Ollama service returned an error. Check the model and try again.") from error

    reply = payload.get("message", {}).get("content")
    if not reply:
        raise RuntimeError("Ollama returned an empty response. Please try again.")
    return reply.strip()


def build_farmer_context(message, farmer_id):
    normalized = message.lower()
    availability_question = any(
        phrase in normalized
        for phrase in ("slot", "available", "booking", "book", "today", "time")
    )
    price_question = any(phrase in normalized for phrase in ("price", "rate", "msp", "market"))
    if not availability_question and not price_question:
        return ""

    today = date_cls.today()
    slots_query = SlotConfig.query.join(Centre).filter(
        Centre.is_active.is_(True),
        SlotConfig.date == today,
        SlotConfig.booked_count < SlotConfig.capacity,
    )
    centres = Centre.query.filter_by(is_active=True).all()
    mentioned_centre = next(
        (centre for centre in centres if centre.name.lower() in normalized),
        None,
    )
    if mentioned_centre:
        slots_query = slots_query.filter(SlotConfig.centre_id == mentioned_centre.id)

    slots = slots_query.order_by(SlotConfig.centre_id.asc(), SlotConfig.time_slot.asc()).all()
    lines = [f"Database date: {today.isoformat()}."]
    if mentioned_centre:
        lines.append(f"Requested centre: {mentioned_centre.name}.")
    if slots:
        lines.append("Available slots today:")
        for slot in slots[:16]:
            lines.append(
                f"- {slot.centre.name}: {slot.time_slot}, "
                f"{slot.available} places remaining out of {slot.capacity}."
            )
    else:
        lines.append("No available slots were found for today in the requested scope.")

    if price_question:
        prices_query = MandiPrice.query.filter(
            db.or_(MandiPrice.centre_id == (mentioned_centre.id if mentioned_centre else None), MandiPrice.centre_id.is_(None))
        )
        prices = prices_query.order_by(
            db.case((MandiPrice.centre_id == (mentioned_centre.id if mentioned_centre else None), 0), else_=1),
            MandiPrice.effective_date.desc(),
        ).all()
        if prices:
            lines.append("Relevant crop prices:")
            for price in prices[:12]:
                scope = price.centre.name if price.centre else "global fallback"
                lines.append(
                    f"- {price.crop_type} at {scope}: market Rs.{price.market_price_per_quintal:.0f} per quintal, "
                    f"MSP Rs.{price.msp_per_quintal:.0f}."
                )

    own_booking = Booking.query.filter(
        Booking.farmer_id == farmer_id,
        Booking.slot_config.has(date=today),
        Booking.status.in_(["pending", "booked", "serving"]),
    ).order_by(Booking.booked_at.desc()).first()
    if own_booking:
        lines.append(
            f"This farmer has a booking at {own_booking.centre.name}, "
            f"{own_booking.slot_config.time_slot}, status {own_booking.status}, "
            f"approval {own_booking.approval_status}, token {own_booking.token_number}."
        )
    return "\n".join(lines)


def chat_with_farmer(message, history, context="", language="en"):
    language_instruction = (
        f"The farmer selected {LANGUAGE_NAMES.get(language, 'English')}. "
        f"Answer entirely in {LANGUAGE_NAMES.get(language, 'English')}. "
        "Do not switch to English unless the farmer asks for English."
    )
    input_items = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            input_items.append({"role": role, "content": content[:2000]})
    input_items.append({"role": "user", "content": message})

    if current_app.config.get("AI_PROVIDER", "openai") == "ollama":
        input_items[0]["content"] += f"\n\nLANGUAGE REQUIREMENT:\n{language_instruction}"
        if context:
            input_items[0]["content"] += f"\n\nLIVE DATABASE CONTEXT (use this for current answers):\n{context}"
        return _ollama_reply(input_items)

    try:
        instructions = SYSTEM_PROMPT
        instructions += f"\n\nLANGUAGE REQUIREMENT:\n{language_instruction}"
        if context:
            instructions += f"\n\nLIVE DATABASE CONTEXT (use this for current answers):\n{context}"
        response = _openai_client().responses.create(
            model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            instructions=instructions,
            input=input_items[1:],
            max_output_tokens=350,
        )
    except Exception as error:
        from openai import RateLimitError
        if isinstance(error, RateLimitError):
            raise RuntimeError("AI assistant quota or rate limit reached. Please try again later.") from error
        raise
    reply = response.output_text
    if not reply:
        raise RuntimeError("The assistant returned an empty response. Please try again.")
    return reply.strip()