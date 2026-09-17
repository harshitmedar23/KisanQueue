"""
Real-time queue / token logic.

Token numbers are assigned sequentially per centre per day at booking time.
The "queue state" for a centre+date is derived directly from Booking rows
(no separate in-memory store needed for correctness at this scale), which
also makes it durable across app restarts. For production scale, this is a
natural place to introduce Redis as noted in the project README.
"""
from datetime import datetime, date, timedelta

from app.extensions import db, socketio
from app.models import Booking, SlotConfig
from app.services.notification import notify_user


def _room_name(centre_id, date):
    return f"centre_{centre_id}_{date.isoformat()}"


def current_serving_token(centre_id, date):
    booking = Booking.query.filter_by(
        centre_id=centre_id, status="serving"
    ).filter(
        Booking.slot_config.has(date=date)
    ).first()
    return booking.token_number if booking else 0


def _slot_start_hour(time_slot):
    try:
        return int(time_slot.split(":", 1)[0])
    except (AttributeError, ValueError):
        return None


def average_service_minutes(centre_id, hour=None, fallback=5):
    completed = Booking.query.filter_by(centre_id=centre_id, status="completed").filter(
        Booking.serving_started_at.isnot(None), Booking.completed_at.isnot(None)
    ).all()
    durations = []
    for booking in completed:
        if hour is not None and _slot_start_hour(booking.slot_config.time_slot) != hour:
            continue
        minutes = (booking.completed_at - booking.serving_started_at).total_seconds() / 60
        if minutes > 0:
            durations.append(minutes)
    return sum(durations[-20:]) / len(durations[-20:]) if durations else fallback


def estimate_wait_minutes(booking, avg_minutes_per_token=5):
    serving_token = current_serving_token(booking.centre_id, booking.slot_config.date)
    tokens_ahead = max(booking.token_number - serving_token - 1, 0)
    hour = _slot_start_hour(booking.slot_config.time_slot)
    measured_average = average_service_minutes(booking.centre_id, hour, avg_minutes_per_token)
    return round(tokens_ahead * measured_average)


def recommend_slots(centre_id, crop_type=None, limit=3):
    del crop_type  # Crop demand is not yet modeled; capacity is the reliable signal.
    upcoming = SlotConfig.query.filter(
        SlotConfig.centre_id == centre_id,
        SlotConfig.date >= date.today(),
        SlotConfig.date <= date.today() + timedelta(days=7),
        SlotConfig.booked_count < SlotConfig.capacity,
    ).order_by(SlotConfig.date.asc(), SlotConfig.time_slot.asc()).all()
    ranked = []
    for slot in upcoming:
        load = slot.booked_count / slot.capacity if slot.capacity else 1
        hour = _slot_start_hour(slot.time_slot)
        service_minutes = average_service_minutes(centre_id, hour)
        ranked.append((load, slot.date, slot.time_slot, slot, round(slot.booked_count * service_minutes)))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [{"slot": item[3], "estimated_wait": item[4], "load_percent": round(item[0] * 100)} for item in ranked[:limit]]


def next_token_number(centre_id, date):
    last = (
        Booking.query.filter_by(centre_id=centre_id)
        .filter(Booking.slot_config.has(date=date))
        .order_by(Booking.token_number.desc())
        .first()
    )
    return (last.token_number + 1) if last else 1


def _broadcast(centre_id, date):
    serving = current_serving_token(centre_id, date)
    predicted_wait = round(average_service_minutes(centre_id))
    day_bookings = Booking.query.filter_by(centre_id=centre_id).filter(
        Booking.slot_config.has(date=date)
    )
    total = day_bookings.count()
    waiting = day_bookings.filter(Booking.status == "booked").count()
    serving_count = day_bookings.filter(Booking.status == "serving").count()
    completed = day_bookings.filter(Booking.status == "completed").count()
    socketio.emit(
        "queue_update",
        {"centre_id": centre_id, "date": date.isoformat(), "serving_token": serving,
         "total": total, "waiting_count": waiting, "serving_count": serving_count,
         "completed_count": completed, "predicted_wait_minutes": predicted_wait,
         "slots": [
             {"id": slot.id, "booked_count": slot.booked_count,
              "capacity": slot.capacity, "available": slot.available}
             for slot in SlotConfig.query.filter_by(centre_id=centre_id, date=date)
             .order_by(SlotConfig.time_slot.asc()).all()
         ]},
        room=_room_name(centre_id, date),
    )


def broadcast(centre_id, date):
    """Publish the current queue and slot state after an external booking."""
    _broadcast(centre_id, date)


def broadcast_transport_status(centre_id, date, booking_id, status):
    socketio.emit(
        "transport_update",
        {"booking_id": booking_id, "status": status},
        room=_room_name(centre_id, date),
    )


def serve_next(centre_id, date):
    """Mark the current 'serving' booking (if any) completed, and promote the
    next lowest-token 'booked' booking to 'serving'. Returns the new serving
    booking, or None if the queue is empty."""
    current = Booking.query.filter_by(centre_id=centre_id, status="serving").filter(
        Booking.slot_config.has(date=date)
    ).first()
    if current:
        current.status = "completed"
        current.completed_at = datetime.utcnow()
        notify_user(
            current.farmer,
            f"Your procurement (Token #{current.token_number}) at {current.centre.name} "
            f"is complete. Thank you!",
            category="queue",
        )

    nxt = (
        Booking.query.filter_by(centre_id=centre_id, status="booked")
        .filter(Booking.slot_config.has(date=date))
        .order_by(Booking.token_number.asc())
        .first()
    )
    if nxt:
        nxt.status = "serving"
        nxt.serving_started_at = datetime.utcnow()
        notify_user(
            nxt.farmer,
            f"You're up! Token #{nxt.token_number} is now being served at {nxt.centre.name}.",
            category="queue",
        )
        nearby = Booking.query.filter(
            Booking.centre_id == centre_id,
            Booking.status == "booked",
            Booking.token_number > nxt.token_number,
            Booking.token_number <= nxt.token_number + 5,
            Booking.turn_soon_notified.is_(False),
        ).filter(Booking.slot_config.has(date=date)).all()
        for booking in nearby:
            notify_user(
                booking.farmer,
                f"You're within 5 farmers of your turn at {booking.centre.name}. "
                f"Please be ready for token #{booking.token_number}.",
                category="queue",
            )
            booking.turn_soon_notified = True

    db.session.commit()
    _broadcast(centre_id, date)
    return nxt


def mark_no_show(booking):
    booking.status = "no_show"
    db.session.commit()
    _broadcast(booking.centre_id, booking.slot_config.date)


def cancel_booking(booking):
    booking.status = "cancelled"
    booking.slot_config.booked_count = max(booking.slot_config.booked_count - 1, 0)
    db.session.commit()
    _broadcast(booking.centre_id, booking.slot_config.date)
