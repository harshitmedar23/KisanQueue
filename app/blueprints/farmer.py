from datetime import datetime, date as date_cls
import base64
import secrets
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, session, jsonify
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import Centre, SlotConfig, Booking, Notification, MandiPrice, Vehicle, TransportBooking
from app.services.notification import notify_user
from app.services import queue as queue_service
from app.services.audit import record
from app.services.receipt import build_receipt
from app.services.payment import upi_qr_data_uri
from app.services.ai_chat import build_farmer_context, chat_with_farmer
from app.services.gemini_service import ask_farmer_voice
from app.services.voice_assistant import synthesize_speech, transcribe_audio

farmer_bp = Blueprint("farmer", __name__, template_folder="../templates/farmer")


def farmer_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "farmer":
            flash("Please login as a farmer to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@farmer_bp.route("/dashboard")
@login_required
@farmer_required
def dashboard():
    upcoming = (
        current_user.bookings.filter(Booking.status.in_(["pending", "booked", "serving"]))
        .order_by(Booking.booked_at.desc())
        .first()
    )
    history = (
        current_user.bookings.filter(Booking.status.in_(["completed", "no_show", "cancelled"]))
        .order_by(Booking.booked_at.desc())
        .limit(5)
        .all()
    )
    unread_count = current_user.notifications.filter_by(is_read=False).count()
    wait_minutes = None
    queue_serving_token = 0
    tokens_ahead = 0
    if upcoming:
        queue_serving_token = queue_service.current_serving_token(upcoming.centre_id, upcoming.slot_config.date)
        tokens_ahead = max(upcoming.token_number - queue_serving_token - 1, 0)
    if upcoming and upcoming.status == "booked":
        wait_minutes = queue_service.estimate_wait_minutes(
            upcoming, current_app.config["AVG_MINUTES_PER_TOKEN"]
        )
    return render_template(
        "farmer/dashboard.html",
        upcoming=upcoming,
        history=history,
        unread_count=unread_count,
        wait_minutes=wait_minutes,
            queue_serving_token=queue_serving_token,
            tokens_ahead=tokens_ahead,
    )


@farmer_bp.route("/chat", methods=["POST"])
@login_required
@farmer_required
@limiter.limit("20 per hour")
def chat():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    history = payload.get("history", [])
    language = payload.get("language", "en")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Please enter a question."}), 400
    if len(message.strip()) > 1000:
        return jsonify({"error": "Please keep your question under 1,000 characters."}), 400
    if not isinstance(history, list):
        history = []
    if language not in {"en", "hi", "kn"}:
        language = "en"

    try:
        context = build_farmer_context(message.strip(), current_user.id)
        reply = chat_with_farmer(message.strip(), history, context, language)
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        current_app.logger.exception("Farmer chatbot request failed")
        return jsonify({"error": "The assistant is temporarily unavailable. Please try again."}), 502
    return jsonify({"reply": reply})


@farmer_bp.route("/voice-assistant", methods=["POST"])
@login_required
@farmer_required
@limiter.limit("10 per hour")
def voice_assistant():
    payload = request.get_json(silent=True) if request.is_json else request.form
    payload = payload or {}
    language = payload.get("language", "en")
    if language not in {"en", "hi", "kn"}:
        language = "en"

    audio_file = request.files.get("audio")
    max_bytes = current_app.config.get("VOICE_MAX_AUDIO_BYTES", 10 * 1024 * 1024)
    if audio_file and request.content_length and request.content_length > max_bytes:
        return jsonify({"error": "Audio file is too large. Maximum size is 10 MB."}), 413

    try:
        question = payload.get("text", "")
        if audio_file:
            question = transcribe_audio(audio_file, audio_file.filename, language)
        if not isinstance(question, str) or not question.strip():
            return jsonify({"error": "Send text or an audio recording."}), 400
        context = build_farmer_context(question.strip(), current_user.id)
        reply = ask_farmer_voice(question.strip(), language, context)
        audio = synthesize_speech(reply, language)
    except (RuntimeError, ValueError) as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        current_app.logger.exception("Farmer voice assistant request failed")
        return jsonify({"error": "The voice assistant is temporarily unavailable."}), 502

    if request.args.get("output") == "audio":
        return send_file(audio, mimetype="audio/mpeg", as_attachment=False,
                         download_name="kisanqueue-response.mp3")
    return jsonify({
        "transcript": question.strip(),
        "reply": reply,
        "audio_base64": base64.b64encode(audio.getvalue()).decode("ascii"),
        "audio_mimetype": "audio/mpeg",
    })


@farmer_bp.route("/book-slot", methods=["GET", "POST"])
@login_required
@farmer_required
def book_slot():
    centres = Centre.query.filter_by(is_active=True).all()

    if request.method == "POST":
        centre_id = request.form.get("centre_id", type=int)
        slot_config_id = request.form.get("slot_config_id", type=int)
        crop_type = request.form.get("crop_type", "").strip()
        quantity = request.form.get("quantity_kg", type=float)
        transport_requested = request.form.get("transport_requested") == "on"
        pickup_location = request.form.get("pickup_location", "").strip()
        vehicle_type = request.form.get("vehicle_type", "other").strip()

        slot_config = SlotConfig.query.get(slot_config_id)
        if not slot_config or slot_config.centre_id != centre_id:
            flash("Please select a valid centre and slot.", "danger")
            return redirect(url_for("farmer.book_slot"))
        if not crop_type or not quantity or quantity <= 0:
            flash("Please provide a valid crop type and quantity.", "danger")
            return redirect(url_for("farmer.book_slot"))
        if slot_config.available <= 0:
            flash("Sorry, that slot is fully booked. Please choose another.", "warning")
            return redirect(url_for("farmer.book_slot"))

        booking = Booking(
            farmer_id=current_user.id,
            centre_id=centre_id,
            slot_config_id=slot_config.id,
            crop_type=crop_type,
            quantity_kg=quantity,
            token_number=0,
            status="pending",
            approval_status="pending",
            checkin_token=secrets.token_urlsafe(18),
        )
        db.session.add(booking)
        db.session.commit()
        if transport_requested and pickup_location:
            fare_by_type = {"tata_ace": 350.0, "tractor": 500.0, "truck": 900.0, "other": 400.0}
            db.session.add(TransportBooking(
                booking_id=booking.id,
                pickup_location=pickup_location,
                fare_amount=fare_by_type.get(vehicle_type, fare_by_type["other"]),
                status="requested",
            ))
            db.session.commit()
            flash("Transport requested and waiting for centre vehicle assignment.", "info")
        queue_service.broadcast(centre_id, slot_config.date)
        record("booking_created", "booking", booking.id, {"token": booking.token_number})
        db.session.commit()

        notify_user(
            current_user,
            f"Booking request submitted for {booking.centre.name} on {slot_config.date} "
            f"({slot_config.time_slot}). Your request is pending mandi owner approval.",
            category="booking",
        )
        flash("Booking request submitted. Awaiting mandi owner approval.", "info")
        return redirect(url_for("farmer.dashboard"))

    # Slots available today or later, grouped simply by centre for the template
    slots_by_centre = {}
    recommended_by_centre = {}
    for centre in centres:
        slots_by_centre[centre.id] = (
            SlotConfig.query.filter(
                SlotConfig.centre_id == centre.id,
                SlotConfig.date >= date_cls.today(),
            )
            .order_by(SlotConfig.date.asc())
            .all()
        )
        recommended_by_centre[centre.id] = [
            {
                "id": item["slot"].id,
                "date": item["slot"].date.isoformat(),
                "time_slot": item["slot"].time_slot,
                "estimated_wait": item["estimated_wait"],
                "load_percent": item["load_percent"],
            }
            for item in queue_service.recommend_slots(centre.id)
        ]

    return render_template(
        "farmer/book_slot.html", centres=centres, slots_by_centre=slots_by_centre,
        recommended_by_centre=recommended_by_centre
    )


@farmer_bp.route("/booking/<int:booking_id>/cancel", methods=["POST"])
@login_required
@farmer_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.farmer_id != current_user.id:
        flash("You can only cancel your own bookings.", "danger")
        return redirect(url_for("farmer.dashboard"))
    if booking.status != "booked":
        flash("Only bookings that haven't started can be cancelled.", "warning")
        return redirect(url_for("farmer.dashboard"))
    queue_service.cancel_booking(booking)
    flash("Booking cancelled.", "info")
    return redirect(url_for("farmer.dashboard"))


@farmer_bp.route("/queue-status/<int:booking_id>")
@login_required
@farmer_required
def queue_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.farmer_id != current_user.id:
        flash("You can only view your own queue status.", "danger")
        return redirect(url_for("farmer.dashboard"))
    serving_token = queue_service.current_serving_token(booking.centre_id, booking.slot_config.date)
    wait_minutes = queue_service.estimate_wait_minutes(
        booking, current_app.config["AVG_MINUTES_PER_TOKEN"]
    )
    predicted_wait_minutes = queue_service.estimate_wait_minutes(
        booking, current_app.config["AVG_MINUTES_PER_TOKEN"]
    )
    return render_template(
        "farmer/queue_status.html",
        booking=booking,
        serving_token=serving_token,
        wait_minutes=wait_minutes,
        predicted_wait_minutes=predicted_wait_minutes,
    )


@farmer_bp.route("/tracker/<int:booking_id>")
@login_required
@farmer_required
def tracker(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.farmer_id != current_user.id:
        flash("You can only view your own bookings.", "danger")
        return redirect(url_for("farmer.dashboard"))
    upi_vpa = current_app.config.get("UPI_VPA", "").strip()
    procurement_qr = None
    if upi_vpa and booking.payment_status != "paid" and booking.estimated_payment:
        procurement_qr = upi_qr_data_uri(
            upi_vpa, current_app.config["UPI_PAYEE_NAME"],
            booking.estimated_payment, f"Procurement token {booking.token_number}",
            f"PROC-{booking.id}",
        )
    transport_qr = None
    if upi_vpa and booking.transport_booking and booking.transport_booking.payment_status != "paid":
        transport_qr = upi_qr_data_uri(
            upi_vpa, current_app.config["UPI_PAYEE_NAME"],
            booking.transport_booking.fare_amount, f"Transport token {booking.token_number}",
            f"TRANS-{booking.transport_booking.id}",
        )
    return render_template("farmer/tracker.html", booking=booking,
                           procurement_qr=procurement_qr, transport_qr=transport_qr,
                           upi_vpa=upi_vpa)


@farmer_bp.route("/history")
@login_required
@farmer_required
def history():
    bookings = current_user.bookings.order_by(Booking.booked_at.desc()).all()
    return render_template("farmer/history.html", bookings=bookings)


@farmer_bp.route("/booking/<int:booking_id>/receipt")
@login_required
@farmer_required
def receipt(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.farmer_id != current_user.id:
        flash("You can only download your own receipt.", "danger")
        return redirect(url_for("farmer.history"))
    return send_file(build_receipt(booking), as_attachment=True,
                     download_name=f"procurement-receipt-{booking.token_number}.pdf",
                     mimetype="application/pdf")


@farmer_bp.route("/prices")
@login_required
@farmer_required
def prices():
    selected_centre_id = request.args.get("centre_id", type=int)
    centres = Centre.query.filter_by(is_active=True).order_by(Centre.name.asc()).all()
    if selected_centre_id is None and centres:
        selected_centre_id = centres[0].id
    snapshots = MandiPrice.query.filter(
        db.or_(MandiPrice.centre_id == selected_centre_id, MandiPrice.centre_id.is_(None))
    ).order_by(
        MandiPrice.crop_type.asc(),
        db.case((MandiPrice.centre_id == selected_centre_id, 0), else_=1),
        MandiPrice.id.desc(),
    ).all()
    latest = {}
    trend_data = {}
    for snapshot in snapshots:
        trend_data.setdefault(snapshot.crop_type, []).append(snapshot.market_price_per_quintal)
        latest.setdefault(snapshot.crop_type, snapshot)

    prices = list(latest.values())
    for price in prices:
        previous = MandiPrice.query.filter(
            MandiPrice.crop_type == price.crop_type,
            MandiPrice.id < price.id,
        ).order_by(MandiPrice.id.desc()).first()
        price.previous_market_price = previous.market_price_per_quintal if previous else None
        price.price_change = round(
            price.market_price_per_quintal - previous.market_price_per_quintal, 2
        ) if previous else None
        price.price_direction = "up" if price.price_change and price.price_change > 0 else (
            "down" if price.price_change and price.price_change < 0 else "steady"
        )
        trend_data[price.crop_type] = list(reversed(trend_data[price.crop_type][:7]))

    return render_template("farmer/prices.html", prices=prices, trend_data=trend_data,
                           centres=centres, selected_centre_id=selected_centre_id)


@farmer_bp.route("/language/<language>")
def language(language):
    if language in {"en", "hi", "kn"}:
        session["language"] = language
    return redirect(request.referrer or url_for("index"))


@farmer_bp.route("/notifications")
@login_required
@farmer_required
def notifications():
    notes = current_user.notifications.order_by(Notification.created_at.desc()).all()
    current_user.notifications.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()

    telegram_deep_link = None
    bot_username = current_app.config.get("TELEGRAM_BOT_USERNAME")
    if current_app.config.get("TELEGRAM_ENABLED") and bot_username and not current_user.telegram_linked:
        code = current_user.generate_telegram_link_code()
        db.session.commit()
        telegram_deep_link = f"https://t.me/{bot_username}?start={code}"

    return render_template(
        "farmer/notifications.html",
        notifications=notes,
        telegram_enabled=current_app.config.get("TELEGRAM_ENABLED"),
        telegram_deep_link=telegram_deep_link,
        telegram_link_code=current_user.telegram_link_code,
    )


@farmer_bp.route("/telegram/unlink", methods=["POST"])
@login_required
@farmer_required
def unlink_telegram():
    current_user.telegram_chat_id = None
    db.session.commit()
    flash("Telegram has been unlinked. You'll no longer get updates there.", "info")
    return redirect(url_for("farmer.notifications"))
