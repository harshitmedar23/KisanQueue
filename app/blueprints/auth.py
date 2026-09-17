import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.extensions import limiter
from app.models import User, OTP
from app.services.validation import is_valid_mobile_number
from app.services.notification import send_sms_number

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


def _issue_otp(mobile_number, purpose, payload=None):
    otp = OTP.create(
        mobile_number=mobile_number,
        purpose=purpose,
        minutes_valid=current_app.config["OTP_EXPIRY_MINUTES"],
        payload=json.dumps(payload) if payload else None,
    )
    session["otp_mobile"] = mobile_number
    session["otp_purpose"] = purpose
    if current_app.config.get("OTP_DEMO_MODE"):
        flash(f"Demo mode: your OTP is {otp.code} (in production this arrives via SMS).", "info")
    else:
        sent = send_sms_number(
            mobile_number,
            f"Your Farmer Procurement OTP is {otp.code}. It expires in {current_app.config['OTP_EXPIRY_MINUTES']} minutes.",
            content_variables={"1": otp.code},
        )
        if sent:
            flash("An OTP has been sent to your mobile number.", "info")
        else:
            flash(
                f"SMS delivery is unavailable right now. Demo OTP: {otp.code}",
                "warning",
            )
    return otp


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.post_login_redirect"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile_number", "").strip()
        email = request.form.get("email", "").strip() or None
        # Public registration must never be able to create staff accounts.
        role = "farmer"

        if not name or not mobile:
            flash("Name and mobile number are required.", "danger")
            return redirect(url_for("auth.register"))
        if not is_valid_mobile_number(mobile):
            flash("Enter a valid 10-digit Indian mobile number beginning with 6, 7, 8, or 9.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(mobile_number=mobile).first():
            flash("This mobile number is already registered. Please login instead.", "warning")
            return redirect(url_for("auth.login"))

        _issue_otp(mobile, "register", payload={"name": name, "email": email, "role": role})
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.post_login_redirect"))

    if request.method == "GET":
        session.pop("otp_mobile", None)
        session.pop("otp_purpose", None)

    if request.method == "POST":
        mobile = request.form.get("mobile_number", "").strip()
        if not is_valid_mobile_number(mobile):
            flash("Enter a valid 10-digit Indian mobile number beginning with 6, 7, 8, or 9.", "danger")
            return redirect(url_for("auth.login"))
        user = User.query.filter_by(mobile_number=mobile).first()
        if not user:
            flash("No account found with that mobile number. Please register first.", "warning")
            return redirect(url_for("auth.register"))
        if not user.is_active:
            flash("This account has been deactivated. Please contact the admin.", "warning")
            return redirect(url_for("auth.login"))

        _issue_otp(mobile, "login")
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/login.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
@limiter.limit("10 per 10 minutes", methods=["POST"])
def verify_otp():
    mobile = session.get("otp_mobile")
    purpose = session.get("otp_purpose")
    if not mobile or not purpose:
        flash("Please start the login/registration process again.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("otp", "").strip()
        otp = (
            OTP.query.filter_by(mobile_number=mobile, purpose=purpose, consumed=False)
            .order_by(OTP.id.desc())
            .first()
        )
        if not otp or not otp.is_valid(code):
            flash("Invalid or expired OTP. Please try again.", "danger")
            return redirect(url_for("auth.verify_otp"))

        otp.consumed = True
        db.session.commit()

        if purpose == "register":
            payload = json.loads(otp.payload) if otp.payload else {}
            user = User(
                name=payload.get("name"),
                mobile_number=mobile,
                email=payload.get("email"),
                role=payload.get("role", "farmer"),
            )
            db.session.add(user)
            db.session.commit()
            flash(f"Welcome, {user.name}! Your account has been created.", "success")
        else:
            user = User.query.filter_by(mobile_number=mobile).first()
            if not user or not user.is_active:
                flash("This account is not active or is no longer authorised to log in.", "warning")
                return redirect(url_for("auth.login"))
            flash(f"Welcome back, {user.name}!", "success")

        session.pop("otp_mobile", None)
        session.pop("otp_purpose", None)
        login_user(user)
        return redirect(url_for("auth.post_login_redirect"))

    return render_template("auth/verify_otp.html", mobile=mobile)


@auth_bp.route("/resend-otp")
@limiter.limit("3 per 10 minutes")
def resend_otp():
    mobile = session.get("otp_mobile")
    purpose = session.get("otp_purpose")
    if not mobile or not purpose:
        return redirect(url_for("auth.login"))
    _issue_otp(mobile, purpose)
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/post-login-redirect")
@login_required
def post_login_redirect():
    if current_user.role in ("admin", "mandi_owner", "staff"):
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("farmer.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("otp_mobile", None)
    session.pop("otp_purpose", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
