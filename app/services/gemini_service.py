"""Server-side Gemini integration for the voice assistant."""
from flask import current_app


FARMER_VOICE_SYSTEM_PROMPT = """You are KisanQueue's voice assistant for farmers.
Answer in the language requested by the farmer. Be concise, practical, and easy to
understand when heard aloud. Help with agriculture, crops, soil, irrigation, pests,
harvesting, storage, mandi prices, MSP, slot booking, queue tokens, payments,
transport, and procurement-centre visits. Do not invent live prices, weather, slot
availability, queue position, or government rules. Say when the farmer should check
the app or contact the local mandi. Never claim to have changed a booking, approved a
slot, assigned a driver, or processed a payment. Never ask for OTPs, passwords, API
keys, or other secrets.
"""


def _client():
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("GEMINI_API_KEY is not configured. Add it to the .env file.")
    from google import genai
    return genai.Client(api_key=api_key)


def query_gemini(prompt: str) -> str:
    """Send one farmer voice prompt to Gemini and return plain text."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")
    response = _client().models.generate_content(
        model=current_app.config.get("GEMINI_MODEL", "gemini-3.6-flash"),
        contents=prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text.strip()


def ask_farmer_voice(question: str, language: str = "en", context: str = "") -> str:
    language_names = {"en": "English", "hi": "Hindi", "kn": "Kannada"}
    selected_language = language_names.get(language, "English")
    prompt = (
        f"{FARMER_VOICE_SYSTEM_PROMPT}\n\n"
        f"Respond entirely in {selected_language}. This response will be read aloud.\n"
    )
    if context:
        prompt += f"\nRead-only live application context:\n{context}\n"
    prompt += f"\nFarmer question:\n{question.strip()}"
    return query_gemini(prompt)
