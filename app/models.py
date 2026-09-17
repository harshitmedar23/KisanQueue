import random
import string
from datetime import datetime, timedelta

from flask_login import UserMixin

from app.extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    mobile_number = db.Column(db.String(15), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="farmer")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    assigned_centre_id = db.Column(db.Integer, db.ForeignKey("centres.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_centre = db.relationship("Centre", foreign_keys=[assigned_centre_id], backref="assigned_staff")

    # --- Telegram notifications ---
    telegram_chat_id = db.Column(db.String(32), nullable=True, unique=True)
    # One-time 6-char code the farmer sends to the bot (/register <code>) to link
    # their Telegram account. Cleared once linking succeeds.
    telegram_link_code = db.Column(db.String(10), nullable=True, unique=True)

    bookings = db.relationship("Booking", backref="farmer", lazy="dynamic",
                                foreign_keys="Booking.farmer_id")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic")
    push_subscriptions = db.relationship("PushSubscription", backref="user", lazy="dynamic")

    def is_admin(self):
        return self.role == "admin"

    def is_staff(self):
        return self.role == "staff"

    def is_mandi_owner(self):
        return self.role == "mandi_owner"

    def is_driver(self):
        return self.role == "driver"

    def can_manage_centre(self, centre_id):
        if self.is_admin():
            return True
        if self.is_mandi_owner() and self.assigned_centre_id == centre_id:
            return True
        if self.is_staff() and self.assigned_centre_id == centre_id:
            return True
        return False

    @property
    def telegram_linked(self):
        return bool(self.telegram_chat_id)

    def generate_telegram_link_code(self):
        """(Re)generate the one-time code the farmer sends to the Telegram bot."""
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(alphabet, k=6))
            if not User.query.filter_by(telegram_link_code=code).first():
                self.telegram_link_code = code
                return code


class OTP(db.Model):
    __tablename__ = "otps"

    id = db.Column(db.Integer, primary_key=True)
    mobile_number = db.Column(db.String(15), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)  # 'register' or 'login'
    payload = db.Column(db.Text, nullable=True)  # JSON string, e.g. pending registration data
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_code():
        return "".join(random.choices(string.digits, k=6))

    def is_valid(self, code):
        return (
            not self.consumed
            and self.code == code
            and self.expires_at >= datetime.utcnow()
        )

    @classmethod
    def create(cls, mobile_number, purpose, minutes_valid=5, payload=None):
        code = cls.generate_code()
        otp = cls(
            mobile_number=mobile_number,
            code=code,
            purpose=purpose,
            payload=payload,
            expires_at=datetime.utcnow() + timedelta(minutes=minutes_valid),
        )
        db.session.add(otp)
        db.session.commit()
        return otp


class Centre(db.Model):
    __tablename__ = "centres"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    slot_configs = db.relationship("SlotConfig", backref="centre", lazy="dynamic")
    bookings = db.relationship("Booking", backref="centre", lazy="dynamic")


class SlotConfig(db.Model):
    """Number of available booking slots for a centre on a given date/time window."""
    __tablename__ = "slot_configs"

    id = db.Column(db.Integer, primary_key=True)
    centre_id = db.Column(db.Integer, db.ForeignKey("centres.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)  # e.g. "09:00 - 11:00"
    capacity = db.Column(db.Integer, nullable=False, default=20)
    booked_count = db.Column(db.Integer, nullable=False, default=0)

    bookings = db.relationship("Booking", backref="slot_config", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("centre_id", "date", "time_slot", name="uq_centre_date_slot"),
    )

    @property
    def available(self):
        return max(self.capacity - self.booked_count, 0)


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    centre_id = db.Column(db.Integer, db.ForeignKey("centres.id"), nullable=False)
    slot_config_id = db.Column(db.Integer, db.ForeignKey("slot_configs.id"), nullable=False)

    crop_type = db.Column(db.String(80), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    token_number = db.Column(db.Integer, nullable=False, default=0)

    # pending -> approved -> booked -> serving -> completed
    # rejected / no_show / cancelled are terminal states
    status = db.Column(db.String(20), nullable=False, default="pending")
    approval_status = db.Column(db.String(20), nullable=False, default="pending")
    rejection_reason = db.Column(db.String(200), nullable=True)
    payment_status = db.Column(db.String(20), nullable=False, default="pending")  # pending/paid
    payment_amount = db.Column(db.Float, nullable=True)
    payment_method = db.Column(db.String(20), nullable=True)
    payment_reference = db.Column(db.String(120), nullable=True)
    turn_soon_notified = db.Column(db.Boolean, nullable=False, default=False)
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    serving_started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    checkin_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    transport_booking = db.relationship("TransportBooking", backref="booking", uselist=False,
                                        cascade="all, delete-orphan")

    @property
    def estimated_payment(self):
        price = MandiPrice.query.filter(
            MandiPrice.crop_type == self.crop_type,
            db.or_(MandiPrice.centre_id == self.centre_id, MandiPrice.centre_id.is_(None)),
        ).order_by(
            db.case((MandiPrice.centre_id == self.centre_id, 0), else_=1),
            MandiPrice.effective_date.desc(),
        ).first()
        return round(self.quantity_kg / 100 * price.market_price_per_quintal, 2) if price else None

    def timeline(self):
        steps = [
            {"label": "Slot Booked", "done": True, "at": self.booked_at},
            {"label": "Called for Procurement", "done": self.serving_started_at is not None,
             "at": self.serving_started_at},
            {"label": "Procurement Completed", "done": self.completed_at is not None,
             "at": self.completed_at},
            {"label": "Payment Received", "done": self.payment_status == "paid",
             "at": self.paid_at},
        ]
        if self.status == "no_show":
            steps.append({"label": "Marked No-Show", "done": True, "at": None})
        if self.status == "cancelled":
            steps.append({"label": "Cancelled", "done": True, "at": None})
        return steps


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    driver_name = db.Column(db.String(120), nullable=False)
    driver_phone = db.Column(db.String(15), nullable=False)
    capacity_kg = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    centre_id = db.Column(db.Integer, db.ForeignKey("centres.id"), nullable=True)
    driver_status = db.Column(db.String(20), nullable=False, default="available")
    assigned_booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True)
    transport_bookings = db.relationship("TransportBooking", backref="vehicle", lazy="dynamic")
    centre = db.relationship("Centre", foreign_keys=[centre_id], backref="vehicles")


class TransportBooking(db.Model):
    __tablename__ = "transport_bookings"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)
    pickup_location = db.Column(db.Text, nullable=False)
    estimated_distance_km = db.Column(db.Float, nullable=True)
    fare_amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default="pending")
    status = db.Column(db.String(20), nullable=False, default="requested")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_active(self):
        return self.status in {"requested", "assigned", "on_the_way", "arrived"}


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(30), default="info")  # info, booking, queue, payment
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PushSubscription(db.Model):
    """Stores a browser's web-push subscription (endpoint + keys) for a user."""
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subscription_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MandiPrice(db.Model):
    __tablename__ = "mandi_prices"

    id = db.Column(db.Integer, primary_key=True)
    centre_id = db.Column(db.Integer, db.ForeignKey("centres.id"), nullable=True, index=True)
    crop_type = db.Column(db.String(80), nullable=False, index=True)
    market_name = db.Column(db.String(120), nullable=False)
    msp_per_quintal = db.Column(db.Float, nullable=False)
    market_price_per_quintal = db.Column(db.Float, nullable=False)
    effective_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    centre = db.relationship("Centre", backref="mandi_prices")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    actor = db.relationship("User", foreign_keys=[actor_id])
