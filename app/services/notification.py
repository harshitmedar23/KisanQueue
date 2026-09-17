"""
Notification service.

- Email via Flask-Mail is the primary fallback channel.
- Web Push (pywebpush) is the primary channel when the farmer has a browser
  subscription registered.
- Telegram is a first-class channel once the farmer links their account (see
  app/services/telegram_bot.py) -- gated behind config.TELEGRAM_ENABLED.
- SMS via Twilio exists but is gated behind config.SMS_ENABLED (disabled by
  default, per spec) -- kept off in favour of Telegram for now.

Every notification is always recorded in the Notification table so it shows
up in the farmer's in-app notifications panel regardless of whether the
external channels succeed (e.g. no SMTP creds configured in a dev sandbox).
"""
import json
import logging

import requests
from flask import current_app
from flask_mail import Message

from app.extensions import db, mail
from app.models import Notification, PushSubscription

logger = logging.getLogger(__name__)

try:
    from pywebpush import webpush, WebPushException
except ImportError:  # pywebpush not installed / not needed in this environment
    webpush = None
    WebPushException = Exception

try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None


def _record_in_app(user, message, category):
    note = Notification(user_id=user.id, message=message, category=category)
    db.session.add(note)
    db.session.commit()
    return note


def _send_email(user, subject, message):
    if not user.email:
        return
    try:
        msg = Message(subject=subject, recipients=[user.email], body=message)
        mail.send(msg)
    except Exception as exc:  # pragma: no cover - best effort, never blocks the app
        logger.info("Email not sent (%s). Suppressed/unconfigured mail server.", exc)


def _send_web_push(user, message):
    if webpush is None:
        return
    private_key = current_app.config.get("VAPID_PRIVATE_KEY")
    if not private_key:
        return
    claim_email = current_app.config.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")
    for sub in user.push_subscriptions:
        try:
            webpush(
                subscription_info=json.loads(sub.subscription_json),
                data=json.dumps({"title": "Procurement Update", "body": message}),
                vapid_private_key=private_key,
                vapid_claims={"sub": claim_email},
            )
        except WebPushException as exc:  # pragma: no cover
            logger.info("Web push failed for user %s: %s", user.id, exc)


def _send_telegram(user, message):
    if not current_app.config.get("TELEGRAM_ENABLED"):
        return
    if not user.telegram_chat_id:
        return
    token = current_app.config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": user.telegram_chat_id, "text": f"🌾 {message}"},
            timeout=5,
        )
        if not resp.ok:
            logger.info("Telegram send failed for user %s: %s", user.id, resp.text)
    except requests.RequestException as exc:  # pragma: no cover - best effort
        logger.info("Telegram send error for user %s: %s", user.id, exc)


def _send_sms(user, message):
    if not current_app.config.get("SMS_ENABLED"):
        return
    if TwilioClient is None:
        return
    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_number = current_app.config.get("TWILIO_PHONE_NUMBER")
    if not (sid and token and from_number):
        return
    try:
        client = TwilioClient(sid, token)
        client.messages.create(body=message, from_=from_number, to=_normalise_mobile(user.mobile_number))
    except Exception as exc:  # pragma: no cover
        logger.info("SMS not sent: %s", exc)


def _normalise_mobile(mobile_number):
    number = str(mobile_number).strip()
    return number if number.startswith("+") else f"+91{number}"


def send_sms_number(mobile_number, message, content_variables=None):
    """Send an SMS to a raw Indian mobile number when Twilio is enabled."""
    if not current_app.config.get("SMS_ENABLED") or TwilioClient is None:
        return False
    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_number = current_app.config.get("TWILIO_PHONE_NUMBER")
    if not (sid and token and from_number):
        return False

    payload = {"from_": from_number, "to": _normalise_mobile(mobile_number)}
    content_sid = current_app.config.get("TWILIO_CONTENT_SID")
    client = None

    try:
        client = TwilioClient(sid, token)
        if content_sid:
            payload["content_sid"] = content_sid
            payload["content_variables"] = json.dumps(content_variables or {})
            client.messages.create(**payload)
            return True
        payload["body"] = message
        client.messages.create(**payload)
        return True
    except Exception as exc:  # pragma: no cover
        error_message = getattr(exc, "msg", str(exc))
        status_code = getattr(exc, "status", None) or "unknown"
        logger.error(
            "Twilio SMS failed for %s: %s (status code: %s)",
            mobile_number,
            error_message,
            status_code,
        )
        if content_sid:
            try:
                payload = {"from_": from_number, "to": _normalise_mobile(mobile_number), "body": message}
                if client is None:
                    client = TwilioClient(sid, token)
                client.messages.create(**payload)
                logger.info("Twilio plain SMS fallback succeeded for %s", mobile_number)
                return True
            except Exception as fallback_exc:  # pragma: no cover
                fallback_message = getattr(fallback_exc, "msg", str(fallback_exc))
                fallback_status = getattr(fallback_exc, "status", None) or "unknown"
                logger.error(
                    "Twilio plain SMS fallback failed for %s: %s (status code: %s)",
                    mobile_number,
                    fallback_message,
                    fallback_status,
                )
                return False
        return False


def notify_user(user, message, category="info", subject="Farmer Procurement Update"):
    """Record an in-app notification and best-effort push it out every enabled channel."""
    note = _record_in_app(user, message, category)
    _send_web_push(user, message)
    _send_email(user, subject, message)
    _send_telegram(user, message)
    _send_sms(user, message)  # no-op unless SMS_ENABLED=True
    return note
