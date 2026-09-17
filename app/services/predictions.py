"""Small, explainable prediction helpers based on existing booking history."""
from datetime import date, timedelta

from app.models import Booking


def no_show_risk(booking):
    history = Booking.query.filter(
        Booking.farmer_id == booking.farmer_id,
        Booking.id != booking.id,
        Booking.status.in_(["completed", "no_show", "cancelled"]),
    ).all()
    if not history:
        return "Low"

    no_shows = sum(item.status == "no_show" for item in history)
    rate = no_shows / len(history)
    if len(history) >= 3 and rate > 0.3:
        return "High"
    if rate > 0.1:
        return "Medium"
    return "Low"


def forecast_next_day(centre_id):
    """Average crop bookings across the last four matching weekdays."""
    tomorrow = date.today() + timedelta(days=1)
    matching_dates = [tomorrow - timedelta(days=7 * index) for index in range(1, 5)]
    observations = []
    for sample_date in matching_dates:
        bookings = Booking.query.filter_by(centre_id=centre_id).filter(
            Booking.slot_config.has(date=sample_date),
            Booking.status != "cancelled",
        ).all()
        if bookings:
            observations.append(bookings)

    if len(observations) < 2:
        return None

    crop_counts = {}
    for bookings in observations:
        daily_counts = {}
        for booking in bookings:
            daily_counts[booking.crop_type] = daily_counts.get(booking.crop_type, 0) + 1
        for crop, count in daily_counts.items():
            crop_counts.setdefault(crop, []).append(count)

    return {
        crop: round(sum(counts) / len(observations), 1)
        for crop, counts in crop_counts.items()
    }
