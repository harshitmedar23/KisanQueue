"""Optional live mandi-price synchronization."""
from datetime import date
import time

import requests
from flask import current_app

from app.extensions import db
from app.models import MandiPrice


_last_sync_at = 0.0


def sync_live_prices():
    """Fetch configured market data and update matching stored crop prices.

    The API response is expected to contain a ``records`` list. Field names can
    be changed through configuration because market APIs use different schemas.
    """
    global _last_sync_at
    url = current_app.config.get("MANDI_API_URL")
    api_key = current_app.config.get("MANDI_API_KEY")
    if not url or not api_key:
        return 0
    now = time.monotonic()
    interval = current_app.config.get("MANDI_API_SYNC_INTERVAL_SECONDS", 900)
    if now - _last_sync_at < interval:
        return 0
    _last_sync_at = now

    params = {
        "api-key": api_key,
        "format": "json",
        "limit": current_app.config.get("MANDI_API_LIMIT", 100),
    }
    try:
        response = requests.get(
            url,
            params=params,
            timeout=current_app.config.get("MANDI_API_TIMEOUT_SECONDS", 2),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        current_app.logger.warning("Live mandi price sync failed: %s", exc)
        return 0
    records = response.json().get("records", [])
    crop_field = current_app.config.get("MANDI_API_CROP_FIELD", "commodity")
    market_field = current_app.config.get("MANDI_API_MARKET_FIELD", "market")
    price_field = current_app.config.get("MANDI_API_PRICE_FIELD", "modal_price")

    updated = 0
    for record in records:
        crop_name = str(record.get(crop_field, "")).strip()
        market_price = _number(record.get(price_field))
        if not crop_name or market_price is None:
            continue
        price = _find_crop_price(crop_name)
        if not price:
            continue
        price.market_price_per_quintal = market_price * 100 if market_price < 1000 else market_price
        price.market_name = str(record.get(market_field) or price.market_name).strip()
        price.effective_date = date.today()
        updated += 1

    if updated:
        db.session.commit()
    return updated


def _find_crop_price(crop_name):
    normalized = crop_name.casefold()
    for price in MandiPrice.query.filter(MandiPrice.centre_id.is_(None)).all():
        if price.crop_type.casefold() == normalized:
            return price
        if price.crop_type == "Rice (Paddy)" and normalized in {"rice", "paddy", "rice (paddy)"}:
            return price
    return None


def _number(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
