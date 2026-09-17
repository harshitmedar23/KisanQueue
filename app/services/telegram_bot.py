"""
Telegram bot worker.

Runs a simple long-polling loop against Telegram's getUpdates API (no
webhook / public URL needed, which is what you want for local + demo use).

Flow:
  1. Farmer logs into the web app -> Notifications page -> "Link Telegram"
     -> we generate a 6-character code (User.telegram_link_code) and show
     a deep link: https://t.me/<bot_username>?start=<code>
  2. Farmer taps it (or messages the bot directly) and sends:
       /start <code>      (Telegram auto-fills this from the deep link)
     or
       /register <code>   (manual fallback if they just open the chat)
  3. The bot looks up the code, stores the chat_id on that User row, clears
     the code, and confirms with a reply. From then on notify_user() will
     deliver to Telegram automatically (see app/services/notification.py).

Run it as its own process, alongside the Flask app:
    python telegram_bot_runner.py
"""
import logging
import time

import requests

from app.extensions import db
from app.models import User

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"
POLL_TIMEOUT = 25  # seconds -- Telegram long-polling; keep under your HTTP client's read timeout


def _api_url(token, method):
    return f"{API_BASE.format(token=token)}/{method}"


def _send(token, chat_id, text):
    try:
        requests.post(
            _api_url(token, "sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except requests.RequestException as exc:  # pragma: no cover - best effort
        logger.warning("Telegram sendMessage failed: %s", exc)


def _handle_message(token, message):
    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()

    if not text.startswith("/"):
        return

    parts = text.split(maxsplit=1)
    command = parts[0].split("@")[0].lower()  # strip "@BotName" suffix if present
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command in ("/start", "/register"):
        if not arg:
            _send(
                token,
                chat_id,
                "👋 Welcome to the Farmer Procurement Assistant!\n\n"
                "To link this chat to your account, log into the web app, "
                "open Notifications -> Link Telegram, and tap the link "
                "shown there (or send /register <code> with the code from that page).",
            )
            return

        code = arg.strip().upper()
        user = User.query.filter_by(telegram_link_code=code).first()
        if not user:
            _send(
                token,
                chat_id,
                "❌ That code isn't valid or has expired. Please generate a "
                "new one from the Notifications page and try again.",
            )
            return

        # If some other account already used this chat, unlink it first.
        existing = User.query.filter_by(telegram_chat_id=chat_id).first()
        if existing and existing.id != user.id:
            existing.telegram_chat_id = None

        user.telegram_chat_id = chat_id
        user.telegram_link_code = None
        db.session.commit()

        _send(
            token,
            chat_id,
            f"✅ Linked! Hi {user.name}, you'll now get booking, queue and "
            "payment updates here on Telegram.",
        )
        return

    if command == "/unlink":
        user = User.query.filter_by(telegram_chat_id=chat_id).first()
        if user:
            user.telegram_chat_id = None
            db.session.commit()
            _send(token, chat_id, "You've been unlinked. Notifications will no longer be sent here.")
        else:
            _send(token, chat_id, "This chat isn't linked to any account.")
        return

    if command == "/status":
        user = User.query.filter_by(telegram_chat_id=chat_id).first()
        if user:
            _send(token, chat_id, f"✅ This chat is linked to {user.name}.")
        else:
            _send(token, chat_id, "This chat isn't linked yet. Send /start <code> from the web app.")
        return

    _send(token, chat_id, "Unknown command. Try /start, /status, or /unlink.")


def run_polling(app):
    """Blocking long-poll loop. Call this from a standalone runner script."""
    token = app.config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set -- bot worker exiting.")
        return

    logger.info("Telegram bot worker started (long polling)...")
    offset = None

    while True:
        try:
            resp = requests.get(
                _api_url(token, "getUpdates"),
                params={"timeout": POLL_TIMEOUT, "offset": offset},
                timeout=POLL_TIMEOUT + 10,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("getUpdates failed, retrying in 5s: %s", exc)
            time.sleep(5)
            continue

        for update in data.get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message")
            if not message:
                continue
            with app.app_context():
                try:
                    _handle_message(token, message)
                except Exception:  # pragma: no cover - never let one bad update kill the loop
                    logger.exception("Error handling Telegram update %s", update.get("update_id"))
