from datetime import datetime, date as date_cls, timedelta
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Centre, SlotConfig, Booking, User, MandiPrice, AuditLog, TransportBooking, Vehicle
from app.services import queue as queue_service
from app.services.notification import notify_user
from app.services.market_data import sync_live_prices
from app.services.audit import record
from app.services.validation import is_valid_mobile_number
from app.services.predictions import no_show_risk, forecast_next_day

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def admin_only_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Please login as an admin to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def centre_access_required(*allowed_roles):
    allowed = set(allowed_roles or ("admin", "mandi_owner", "staff"))

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in allowed:
                flash("You do not have permission to access this resource.", "warning")
                return redirect(url_for("auth.login"))
            centre_id = kwargs.get("centre_id")
            if centre_id is None and request.method == "POST":
                centre_id = request.form.get("centre_id", type=int)
            if current_user.is_admin():
                return f(*args, **kwargs)
            if centre_id is not None and current_user.assigned_centre_id != centre_id:
                flash("You are not authorised to manage that mandi.", "danger")
                return redirect(url_for("admin.dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def owner_or_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ("admin", "mandi_owner"):
            flash("Please login as an admin or mandi owner to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def staff_or_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ("admin", "staff", "mandi_owner"):
            flash("Please login as a staff, owner, or admin to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@admin_bp.route("/dashboard")
@login_required
@staff_or_admin_required
def dashboard():
    centres = Centre.query.filter_by(is_active=True).all()

    if current_user.role in ("staff", "mandi_owner"):
        assigned_centre = Centre.query.get(current_user.assigned_centre_id)
        if assigned_centre is None:
            flash("Your account is not assigned to any mandi centre yet.", "warning")
            return redirect(url_for("auth.logout"))
        centres = [assigned_centre]
        requested_centre_id = str(assigned_centre.id)
    else:
        requested_centre_id = request.args.get("centre_id")

    valid_centre_ids = {str(centre.id) for centre in centres}
    selected_centre_id = (
        requested_centre_id
        if requested_centre_id == "all" or requested_centre_id in valid_centre_ids
        else (str(centres[0].id) if centres else None)
    )
    show_all_centres = selected_centre_id == "all" and current_user.is_admin()
    selected_date_str = request.args.get("date")
    selected_date = (
        datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        if selected_date_str
        else date_cls.today()
    )

    bookings = []
    serving_token = 0
    slots = []
    queue_summary = {"total": 0, "waiting": 0, "serving": 0, "completed": 0}
    upcoming_dates = []
    if selected_centre_id:
        centre_ids = [centre.id for centre in centres] if show_all_centres else [int(selected_centre_id)]
        upcoming_dates = [row[0] for row in db.session.query(SlotConfig.date).join(
            Booking, Booking.slot_config_id == SlotConfig.id
        ).filter(
            Booking.centre_id.in_(centre_ids), SlotConfig.date >= date_cls.today()
        ).distinct().order_by(SlotConfig.date.asc()).limit(14).all()]
        bookings = (
            Booking.query.filter(Booking.centre_id.in_(centre_ids))
            .filter(Booking.slot_config.has(date=selected_date))
            .order_by(Booking.centre_id.asc(), Booking.token_number.asc())
            .all()
        )
        queue_summary = {
            "total": len(bookings),
            "waiting": sum(booking.status == "booked" for booking in bookings),
            "serving": sum(booking.status == "serving" for booking in bookings),
            "completed": sum(booking.status == "completed" for booking in bookings),
        }
        no_show_risks = {booking.id: no_show_risk(booking) for booking in bookings}
        if not show_all_centres:
            serving_token = queue_service.current_serving_token(int(selected_centre_id), selected_date)
            slots = SlotConfig.query.filter_by(
                centre_id=int(selected_centre_id), date=selected_date
            ).order_by(SlotConfig.time_slot.asc()).all()

    return render_template(
        "admin/dashboard.html",
        centres=centres,
        selected_centre_id=selected_centre_id,
        show_all_centres=show_all_centres,
        selected_date=selected_date,
        bookings=bookings,
        serving_token=serving_token,
        slots=slots,
        queue_summary=queue_summary,
        no_show_risks=no_show_risks if selected_centre_id else {},
        upcoming_dates=upcoming_dates,
    )


@admin_bp.route("/owner-dashboard")
@login_required
def owner_dashboard():
    if not current_user.is_mandi_owner():
        flash("Only mandi owners can access the owner dashboard.", "warning")
        return redirect(url_for("auth.post_login_redirect"))
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/booking/<int:booking_id>/decision", methods=["POST"])
@login_required
def booking_decision(booking_id):
    if not current_user.is_mandi_owner():
        flash("Only the assigned mandi owner can approve or reject slot requests.", "warning")
        return redirect(url_for("auth.post_login_redirect"))
    booking = Booking.query.get_or_404(booking_id)
    if booking.centre_id != current_user.assigned_centre_id:
        flash("You can only review bookings for your assigned mandi.", "danger")
        return redirect(url_for("admin.dashboard"))

    action = request.form.get("action", "accept").strip().lower()
    reason = request.form.get("rejection_reason", "").strip()

    if action == "accept":
        already_approved = booking.approval_status == "approved"
        if not already_approved:
            booking.slot_config.booked_count = min(
                booking.slot_config.booked_count + 1,
                booking.slot_config.capacity,
            )
        if not booking.token_number or booking.token_number <= 0:
            booking.token_number = queue_service.next_token_number(booking.centre_id, booking.slot_config.date)
        booking.approval_status = "approved"
        booking.status = "booked"
        booking.approved_at = datetime.utcnow()
        notify_user(
            booking.farmer,
            f"Your booking for {booking.centre.name} on {booking.slot_config.date} ({booking.slot_config.time_slot}) has been accepted. Token #{booking.token_number} is confirmed.",
            category="booking",
        )
        flash("Booking accepted and token confirmed.", "success")
        record("booking_accepted", "booking", booking.id, {"token": booking.token_number, "centre_id": booking.centre_id})
    else:
        booking.approval_status = "rejected"
        booking.status = "rejected"
        booking.rejection_reason = reason or "No reason provided."
        notify_user(
            booking.farmer,
            f"Your booking request for {booking.centre.name} on {booking.slot_config.date} was rejected. {booking.rejection_reason}",
            category="booking",
        )
        flash("Booking rejected and farmer notified.", "info")
        record("booking_rejected", "booking", booking.id, {"centre_id": booking.centre_id, "reason": booking.rejection_reason})

    db.session.commit()
    queue_service.broadcast(booking.centre_id, booking.slot_config.date)
    return redirect(url_for("admin.dashboard", centre_id=booking.centre_id, date=booking.slot_config.date.isoformat()))


@admin_bp.route("/queue/serve-next", methods=["POST"])
@login_required
@staff_or_admin_required
def serve_next():
    centre_id = request.form.get("centre_id", type=int)
    if current_user.role in ("staff", "mandi_owner"):
        centre_id = current_user.assigned_centre_id
    date_str = request.form.get("date")
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    nxt = queue_service.serve_next(centre_id, d)
    record("serve_next", "centre", centre_id, {"date": date_str, "token": nxt.token_number if nxt else None})
    db.session.commit()
    if nxt:
        flash(f"Now serving token #{nxt.token_number} ({nxt.farmer.name}).", "success")
    else:
        flash("No more farmers waiting in the queue for this centre/date.", "info")
    return redirect(url_for("admin.dashboard", centre_id=centre_id, date=date_str))


@admin_bp.route("/booking/<int:booking_id>/no-show", methods=["POST"])
@login_required
@staff_or_admin_required
def mark_no_show(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if current_user.role in ("staff", "mandi_owner") and booking.centre_id != current_user.assigned_centre_id:
        flash("You can only manage bookings from your assigned centre.", "warning")
        return redirect(url_for("admin.dashboard"))
    queue_service.mark_no_show(booking)
    record("marked_no_show", "booking", booking.id)
    db.session.commit()
    flash(f"Token #{booking.token_number} marked as no-show.", "info")
    return redirect(url_for("admin.dashboard", centre_id=booking.centre_id,
                             date=booking.slot_config.date.isoformat()))


@admin_bp.route("/booking/<int:booking_id>/payment", methods=["POST"])
@login_required
@staff_or_admin_required
def update_payment(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if current_user.role in ("staff", "mandi_owner") and booking.centre_id != current_user.assigned_centre_id:
        flash("You can only manage bookings from your assigned centre.", "warning")
        return redirect(url_for("admin.dashboard"))
    amount = booking.estimated_payment
    if not amount:
        flash("Configure a market price for this crop before recording payment.", "danger")
        return redirect(url_for("admin.dashboard", centre_id=booking.centre_id,
                                date=booking.slot_config.date.isoformat()))
    booking.payment_status = "paid"
    booking.payment_amount = amount
    booking.payment_method = request.form.get("payment_method", "cash").strip() or "cash"
    booking.payment_reference = request.form.get("payment_reference", "").strip() or None
    booking.paid_at = datetime.utcnow()
    db.session.commit()
    record("payment_recorded", "booking", booking.id, {"amount": amount, "method": booking.payment_method,
                                                        "reference": booking.payment_reference})
    db.session.commit()
    notify_user(
        booking.farmer,
        f"Payment of Rs.{amount:.2f} for token #{booking.token_number} "
        f"({booking.crop_type}) has been processed.",
        category="payment",
    )
    flash(f"Payment recorded for token #{booking.token_number}.", "success")
    return redirect(url_for("admin.dashboard", centre_id=booking.centre_id,
                             date=booking.slot_config.date.isoformat()))


@admin_bp.route("/booking/<int:booking_id>/transport-status", methods=["POST"])
@login_required
@staff_or_admin_required
def update_transport_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if current_user.role in ("staff", "mandi_owner") and booking.centre_id != current_user.assigned_centre_id:
        flash("You can only manage transport at your assigned centre.", "warning")
        return redirect(url_for("admin.dashboard"))
    transport = TransportBooking.query.filter_by(booking_id=booking.id).first_or_404()
    if booking.approval_status != "approved":
        flash("Transport can be updated after the booking is approved.", "warning")
        return redirect(url_for("admin.dashboard", centre_id=booking.centre_id,
                                date=booking.slot_config.date.isoformat()))
    next_status = request.form.get("status", "").strip()
    allowed = {
        "assigned": "on_the_way",
        "on_the_way": "arrived", "arrived": "completed",
    }
    if allowed.get(transport.status) != next_status:
        flash("Transport status can only move to the next step.", "warning")
    else:
        transport.status = next_status
        transport.updated_at = datetime.utcnow()
        if transport.vehicle:
            if next_status == "on_the_way":
                transport.vehicle.driver_status = "on_trip"
            elif next_status == "completed":
                transport.vehicle.driver_status = "available"
                transport.vehicle.assigned_booking_id = None
        record("transport_status_updated", "transport_booking", transport.id, {"status": next_status})
        db.session.commit()
        queue_service.broadcast_transport_status(booking.centre_id, booking.slot_config.date, booking.id, next_status)
        flash("Transport status updated.", "success")
    return redirect(url_for("admin.dashboard", centre_id=booking.centre_id,
                             date=booking.slot_config.date.isoformat()))


@admin_bp.route("/transport")
@login_required
@staff_or_admin_required
def transport_operations():
    query = TransportBooking.query.join(Booking).order_by(TransportBooking.updated_at.desc())
    if current_user.role in ("staff", "mandi_owner"):
        query = query.filter(Booking.centre_id == current_user.assigned_centre_id)
    transport_bookings = query.all()
    vehicles = Vehicle.query.order_by(Vehicle.is_active.desc(), Vehicle.type.asc(), Vehicle.driver_name.asc()).all()
    return render_template("admin/transport.html", transport_bookings=transport_bookings, vehicles=vehicles)


@admin_bp.route("/vehicles", methods=["POST"])
@login_required
@admin_only_required
def register_vehicle():
    vehicle_type = request.form.get("type", "").strip()
    driver_name = request.form.get("driver_name", "").strip()
    driver_phone = request.form.get("driver_phone", "").strip()
    capacity_kg = request.form.get("capacity_kg", type=float)
    if vehicle_type not in {"tata_ace", "tractor", "truck", "other"} or not driver_name or not driver_phone or not capacity_kg or capacity_kg <= 0:
        flash("Enter a valid vehicle type, driver details, and capacity.", "danger")
    else:
        db.session.add(Vehicle(type=vehicle_type, driver_name=driver_name,
                               driver_phone=driver_phone, capacity_kg=capacity_kg))
        db.session.commit()
        flash("Vehicle and driver registered.", "success")
    return redirect(url_for("admin.transport_operations"))


@admin_bp.route("/vehicles/<int:vehicle_id>/toggle", methods=["POST"])
@login_required
@admin_only_required
def toggle_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    vehicle.is_active = not vehicle.is_active
    db.session.commit()
    flash(f"Vehicle {vehicle.driver_name} is now {'active' if vehicle.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.transport_operations"))


@admin_bp.route("/transport/<int:transport_id>/assign", methods=["POST"])
@login_required
@staff_or_admin_required
def assign_transport_vehicle(transport_id):
    transport = TransportBooking.query.get_or_404(transport_id)
    if current_user.role in ("staff", "mandi_owner") and transport.booking.centre_id != current_user.assigned_centre_id:
        flash("You can only assign transport at your centre.", "warning")
        return redirect(url_for("admin.transport_operations"))
    if transport.booking.approval_status != "approved":
        flash("Approve the farmer booking before assigning transport.", "warning")
        return redirect(url_for("admin.transport_operations"))
    vehicle = Vehicle.query.filter(
        Vehicle.id == request.form.get("vehicle_id", type=int),
        Vehicle.is_active.is_(True),
        db.or_(Vehicle.centre_id == transport.booking.centre_id, Vehicle.centre_id.is_(None)),
    ).first()
    if not vehicle or vehicle.driver_status not in (None, "available"):
        flash("Select an active vehicle with an available driver.", "warning")
    else:
        vehicle.driver_status = "available"
        transport.vehicle_id = vehicle.id
        transport.status = "assigned"
        transport.updated_at = datetime.utcnow()
        if vehicle.centre_id is None:
            vehicle.centre_id = transport.booking.centre_id
        vehicle.driver_status = "assigned"
        vehicle.assigned_booking_id = transport.booking_id
        db.session.commit()
        queue_service.broadcast_transport_status(transport.booking.centre_id, transport.booking.slot_config.date, transport.booking.id, "assigned")
        flash("Vehicle assigned to transport booking.", "success")
    return redirect(url_for("admin.transport_operations"))


@admin_bp.route("/mandi-owners", methods=["GET", "POST"])
@login_required
@admin_only_required
def manage_mandi_owners():
    centres = Centre.query.filter_by(is_active=True).all()
    owners = User.query.filter_by(role="mandi_owner").order_by(User.name.asc()).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile_number", "").strip()
        centre_id = request.form.get("centre_id", type=int)
        if not name or not mobile:
            flash("Owner name and mobile are required.", "danger")
        elif not is_valid_mobile_number(mobile):
            flash("Enter a valid 10-digit Indian mobile number beginning with 6, 7, 8, or 9.", "danger")
        elif not centre_id:
            flash("Select the mandi centre to assign this owner to.", "warning")
        else:
            owner = User.query.filter_by(mobile_number=mobile).first()
            if owner is None:
                owner = User(name=name, mobile_number=mobile, role="mandi_owner", assigned_centre_id=centre_id)
                db.session.add(owner)
            else:
                owner.name = name
                owner.role = "mandi_owner"
                owner.assigned_centre_id = centre_id
            db.session.commit()
            record("mandi_owner_assigned", "user", owner.id, {"centre_id": centre_id})
            flash(f"Mandi owner assigned for {Centre.query.get(centre_id).name if Centre.query.get(centre_id) else 'the selected centre'}.", "success")
            return redirect(url_for("admin.manage_mandi_owners"))

    return render_template("admin/mandi_owners.html", centres=centres, owners=owners)


@admin_bp.route("/mandi-owner/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@admin_only_required
def toggle_mandi_owner_status(user_id):
    owner = User.query.filter_by(id=user_id, role="mandi_owner").first_or_404()
    owner.is_active = not owner.is_active
    db.session.commit()
    record("mandi_owner_status_updated", "user", owner.id, {"is_active": owner.is_active})
    flash(f"Mandi owner {owner.name} is now {'active' if owner.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.manage_mandi_owners"))


@admin_bp.route("/staff/<int:staff_id>/toggle-status", methods=["POST"])
@login_required
def toggle_staff_status(staff_id):
    if current_user.role != "mandi_owner":
        flash("Only mandi owners can update staff status.", "warning")
        return redirect(url_for("auth.login"))
    staff = User.query.filter_by(id=staff_id, role="staff").first_or_404()
    if current_user.role == "mandi_owner" and staff.assigned_centre_id != current_user.assigned_centre_id:
        flash("You can only manage staff from your assigned mandi.", "danger")
        return redirect(url_for("admin.manage_staff"))
    staff.is_active = not staff.is_active
    db.session.commit()
    record("staff_status_updated", "user", staff.id, {"is_active": staff.is_active})
    flash(f"Staff member {staff.name} is now {'active' if staff.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.manage_staff"))


@admin_bp.route("/owner/<int:user_id>/assign-centre", methods=["POST"])
@login_required
@admin_only_required
def assign_owner_centre(user_id):
    owner = User.query.filter_by(id=user_id, role="mandi_owner").first_or_404()
    centre_id = request.form.get("centre_id", type=int)
    centre = Centre.query.filter_by(id=centre_id, is_active=True).first()
    if not centre:
        flash("Please select a valid active centre.", "warning")
        return redirect(url_for("admin.manage_mandi_owners"))
    owner.assigned_centre_id = centre.id
    owner.is_active = True
    db.session.commit()
    record("mandi_owner_centre_updated", "user", owner.id, {"centre_id": centre.id})
    flash(f"{owner.name} is now assigned to {centre.name}.", "success")
    return redirect(url_for("admin.manage_mandi_owners"))


@admin_bp.route("/staff/<int:staff_id>/centre", methods=["POST"])
@login_required
def update_staff_centre(staff_id):
    if current_user.role != "mandi_owner":
        flash("Only mandi owners can update staff centres.", "warning")
        return redirect(url_for("auth.login"))
    staff = User.query.filter_by(id=staff_id, role="staff").first_or_404()
    if current_user.role == "mandi_owner" and staff.assigned_centre_id != current_user.assigned_centre_id:
        flash("You can only reassign staff within your assigned mandi.", "danger")
        return redirect(url_for("admin.manage_staff"))
    centre_id = request.form.get("centre_id", type=int)
    if current_user.role == "mandi_owner":
        centre_id = current_user.assigned_centre_id
    if not centre_id:
        flash("Please select a valid centre for the staff member.", "warning")
        return redirect(url_for("admin.manage_staff"))
    centre = Centre.query.filter_by(id=centre_id, is_active=True).first()
    if not centre:
        flash("The selected centre is not valid or active.", "warning")
        return redirect(url_for("admin.manage_staff"))
    staff.assigned_centre_id = centre_id
    record("staff_centre_updated", "user", staff.id, {"centre_id": centre_id})
    db.session.commit()
    flash(f"Assigned centre updated for {staff.name}.", "success")
    return redirect(url_for("admin.manage_staff"))


@admin_bp.route("/staff", methods=["GET", "POST"])
@login_required
def manage_staff():
    if current_user.role == "admin":
        flash("Admins assign mandi owners. Mandi owners manage their centre staff.", "info")
        return redirect(url_for("admin.manage_mandi_owners"))
    if current_user.role != "mandi_owner":
        flash("Only mandi owners can manage staff.", "warning")
        return redirect(url_for("auth.login"))

    centres = Centre.query.filter_by(is_active=True).all()
    if current_user.role == "mandi_owner":
        centres = [Centre.query.get(current_user.assigned_centre_id)] if current_user.assigned_centre_id else []

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile_number", "").strip()
        email = request.form.get("email", "").strip() or None
        centre_id = request.form.get("centre_id", type=int)
        if current_user.role == "mandi_owner":
            centre_id = current_user.assigned_centre_id
        if not name or not mobile:
            flash("Name and mobile number are required.", "danger")
        elif not is_valid_mobile_number(mobile):
            flash("Enter a valid 10-digit Indian mobile number beginning with 6, 7, 8, or 9.", "danger")
        elif User.query.filter_by(mobile_number=mobile).first():
            flash("That mobile number is already registered.", "warning")
        elif not centre_id:
            flash("Please assign the staff member to a valid centre.", "warning")
        else:
            staff = User(name=name, mobile_number=mobile, email=email, role="staff", assigned_centre_id=centre_id)
            db.session.add(staff)
            db.session.flush()
            record("staff_created", "user", staff.id, {"name": name, "mobile": mobile, "centre_id": centre_id})
            db.session.commit()
            flash(f"Staff account created for {name}. They can now login with OTP.", "success")
            return redirect(url_for("admin.manage_staff"))

    staff_members = User.query.filter_by(role="staff")
    if current_user.role == "mandi_owner" and current_user.assigned_centre_id:
        staff_members = staff_members.filter_by(assigned_centre_id=current_user.assigned_centre_id)
    staff_members = staff_members.order_by(User.name.asc()).all()
    return render_template("admin/staff.html", staff_members=staff_members, centres=centres)


@admin_bp.route("/centres", methods=["POST"])
@login_required
@admin_only_required
def create_centre():
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    if not name:
        flash("Centre name is required.", "danger")
    else:
        centre = Centre(name=name, location=location or None)
        db.session.add(centre)
        db.session.commit()
        record("centre_created", "centre", centre.id, {"name": name, "location": location})
        flash("Procurement centre created.", "success")
    return redirect(url_for("admin.manage_mandi_owners"))


@admin_bp.route("/slots", methods=["GET", "POST"])
@login_required
@admin_only_required
def manage_slots():
    centres = Centre.query.all()

    if request.method == "POST":
        centre_id = request.form.get("centre_id", type=int)
        date_str = request.form.get("date")
        time_slot = request.form.get("time_slot", "").strip()
        capacity = request.form.get("capacity", type=int)

        if not (centre_id and date_str and time_slot and capacity):
            flash("All fields are required to configure a slot.", "danger")
            return redirect(url_for("admin.manage_slots"))

        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        existing = SlotConfig.query.filter_by(centre_id=centre_id, date=d, time_slot=time_slot).first()
        if existing:
            existing.capacity = capacity
            flash("Slot capacity updated.", "success")
        else:
            db.session.add(SlotConfig(centre_id=centre_id, date=d, time_slot=time_slot, capacity=capacity))
            flash("New slot created.", "success")
        record("slot_configured", "centre", centre_id, {"date": date_str, "time_slot": time_slot, "capacity": capacity})
        db.session.commit()
        return redirect(url_for("admin.manage_slots"))

    slot_configs = SlotConfig.query.filter(
        SlotConfig.date >= date_cls.today()
    ).order_by(SlotConfig.date.asc(), SlotConfig.centre_id.asc(), SlotConfig.time_slot.asc()).all()
    return render_template("admin/slots.html", centres=centres, slot_configs=slot_configs,
                            today=date_cls.today().isoformat())


@admin_bp.route("/analytics")
@login_required
@admin_only_required
def analytics():
    total_bookings = Booking.query.count()
    completed = Booking.query.filter_by(status="completed").count()
    no_shows = Booking.query.filter_by(status="no_show").count()
    pending_payments = Booking.query.filter_by(payment_status="pending").count()
    paid_total = db.session.query(db.func.coalesce(db.func.sum(Booking.payment_amount), 0.0)).filter(
        Booking.payment_status == "paid"
    ).scalar()
    completed_waits = Booking.query.filter(
        Booking.serving_started_at.isnot(None), Booking.booked_at.isnot(None)
    ).all()
    average_wait_minutes = round(
        sum((booking.serving_started_at - booking.booked_at).total_seconds() / 60
            for booking in completed_waits) / len(completed_waits), 1
    ) if completed_waits else 0
    waiting_count = Booking.query.filter_by(status="booked").count()

    per_centre = (
        db.session.query(Centre.name, db.func.count(Booking.id))
        .join(Booking, Booking.centre_id == Centre.id)
        .group_by(Centre.name)
        .all()
    )

    chart_labels = [name for name, _ in per_centre]
    chart_values = [count for _, count in per_centre]
    heatmap_start = date_cls.today() - timedelta(days=6)
    heatmap_slots = SlotConfig.query.filter(
        SlotConfig.date.between(heatmap_start, date_cls.today())
    ).all()
    heatmap_slot_names = sorted({slot.time_slot for slot in heatmap_slots})
    heatmap_counts = {
        (centre_id, time_slot): count
        for centre_id, time_slot, count in db.session.query(
            Booking.centre_id, SlotConfig.time_slot, db.func.count(Booking.id)
        ).join(SlotConfig, Booking.slot_config_id == SlotConfig.id)
        .filter(SlotConfig.date.between(heatmap_start, date_cls.today()))
        .group_by(Booking.centre_id, SlotConfig.time_slot)
        .all()
    }
    heatmap_capacity = {}
    for slot in heatmap_slots:
        key = (slot.centre_id, slot.time_slot)
        heatmap_capacity[key] = heatmap_capacity.get(key, 0) + slot.capacity
    heatmap_rows = []
    for centre in Centre.query.filter_by(is_active=True).order_by(Centre.name.asc()).all():
        cells = []
        for time_slot in heatmap_slot_names:
            key = (centre.id, time_slot)
            capacity = heatmap_capacity.get(key, 0)
            count = heatmap_counts.get(key, 0)
            load = round((count / capacity) * 100) if capacity else 0
            cells.append({"load": load, "count": count})
        heatmap_rows.append({"name": centre.name, "cells": cells})
    forecasts = [
        {"name": centre.name, "crops": forecast_next_day(centre.id)}
        for centre in Centre.query.filter_by(is_active=True).order_by(Centre.name.asc()).all()
    ]
    return render_template(
        "admin/analytics.html",
        total_bookings=total_bookings,
        completed=completed,
        no_shows=no_shows,
        pending_payments=pending_payments,
        paid_total=paid_total,
        average_wait_minutes=average_wait_minutes,
        waiting_count=waiting_count,
        per_centre=per_centre,
        chart_labels=chart_labels,
        chart_values=chart_values,
        heatmap_slot_names=heatmap_slot_names,
        heatmap_rows=heatmap_rows,
        forecasts=forecasts,
    )


@admin_bp.route("/prices", methods=["GET", "POST"])
@login_required
@admin_only_required
def manage_prices():
    sync_live_prices()
    centres = Centre.query.filter_by(is_active=True).order_by(Centre.name.asc()).all()
    if request.method == "POST":
        crop_type = request.form.get("crop_type", "").strip()
        market_name = request.form.get("market_name", "Local Mandi").strip()
        centre_id = request.form.get("centre_id", type=int)
        msp = request.form.get("msp_per_quintal", type=float)
        market_price = request.form.get("market_price_per_quintal", type=float)
        if not crop_type or not msp or not market_price:
            flash("Crop and both prices are required.", "danger")
        else:
            db.session.add(MandiPrice(centre_id=centre_id, crop_type=crop_type, market_name=market_name,
                                      msp_per_quintal=msp, market_price_per_quintal=market_price))
            record("price_updated", "mandi_price", details={"crop": crop_type, "centre_id": centre_id})
            db.session.commit()
            flash("Market price added.", "success")
    return render_template("admin/prices.html", prices=MandiPrice.query.order_by(MandiPrice.updated_at.desc()).all(), centres=centres)


@admin_bp.route("/prices/<int:price_id>/edit", methods=["GET", "POST"])
@login_required
@admin_only_required
def edit_price(price_id):
    price = MandiPrice.query.get_or_404(price_id)
    if request.method == "POST":
        market_name = request.form.get("market_name", "").strip()
        msp = request.form.get("msp_per_quintal", type=float)
        market_price = request.form.get("market_price_per_quintal", type=float)
        if not market_name or msp is None or msp < 0 or market_price is None or market_price < 0:
            flash("Enter a market name and valid non-negative prices.", "danger")
        else:
            price.market_name = market_name
            price.msp_per_quintal = msp
            price.market_price_per_quintal = market_price
            price.effective_date = date_cls.today()
            record("price_updated", "mandi_price", entity_id=price.id,
                   details={"crop": price.crop_type})
            db.session.commit()
            flash(f"{price.crop_type} price updated.", "success")
            return redirect(url_for("admin.manage_prices"))
    return render_template("admin/edit_price.html", price=price)


@admin_bp.route("/audit-log")
@login_required
@admin_only_required
def audit_log():
    return render_template("admin/audit_log.html", logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all())


@admin_bp.route("/check-in/<token>", methods=["GET", "POST"])
@login_required
@staff_or_admin_required
def check_in(token):
    booking = Booking.query.filter_by(checkin_token=token).first_or_404()
    if current_user.is_staff() and booking.centre_id != current_user.assigned_centre_id:
        flash("You can only check in farmers from your assigned centre.", "warning")
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        booking.checked_in_at = datetime.utcnow()
        record("farmer_checked_in", "booking", booking.id)
        db.session.commit()
        flash(f"Token #{booking.token_number} checked in.", "success")
    return render_template("admin/check_in.html", booking=booking)
