import os

from flask import Flask, redirect, url_for, session
from flask_login import current_user

from config import Config
from app.extensions import db, login_manager, mail, socketio, migrate, limiter


def _upgrade_legacy_schema():
    """Keep existing demo SQLite files bootable; production uses Flask-Migrate."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    additions = {
        "users": [
            ("telegram_chat_id", "VARCHAR(32)"),
            ("telegram_link_code", "VARCHAR(10)"),
            ("assigned_centre_id", "INTEGER"),
        ],
        "centres": [("latitude", "FLOAT"), ("longitude", "FLOAT")],
        "bookings": [("checkin_token", "VARCHAR(64)"), ("checked_in_at", "DATETIME")],
    }
    for table, columns in additions.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in columns:
            if name not in existing:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
    db.session.commit()


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static")),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db, directory=app.config.get("MIGRATION_DIRECTORY"))
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    mail.init_app(app)
    socketio.init_app(app, async_mode=app.config.get("SOCKETIO_ASYNC_MODE", "threading"),
                       cors_allowed_origins="*")

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.blueprints.auth import auth_bp
    from app.blueprints.farmer import farmer_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(farmer_bp, url_prefix="/farmer")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Registers SocketIO event handlers as a side effect of import.
    from app.sockets import queue_socket  # noqa: F401

    @app.context_processor
    def inject_unread_count():
        language = session.get("language", "en")
        labels = {
            "en": {"dashboard": "Dashboard", "book": "Book Slot", "history": "History", "prices": "Mandi Prices", "notifications": "Notifications", "logout": "Logout", "queue": "Queue Dashboard", "slots": "Manage Slots", "analytics": "Analytics", "audit": "Audit Log", "login": "Login", "register": "Register", "toggle_theme": "Toggle dark mode"},
            "hi": {"dashboard": "डैशबोर्ड", "book": "स्लॉट बुक करें", "history": "इतिहास", "prices": "मंडी भाव", "notifications": "सूचनाएं", "logout": "लॉग आउट", "queue": "कतार डैशबोर्ड", "slots": "स्लॉट प्रबंधन", "analytics": "विश्लेषण", "audit": "ऑडिट लॉग", "login": "लॉगिन", "register": "रजिस्टर", "toggle_theme": "डार्क मोड टॉगल करें"},
            "kn": {"dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "book": "ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ", "history": "ಇತಿಹಾಸ", "prices": "ಮಾರುಕಟ್ಟೆ ದರ", "notifications": "ಸೂಚನೆಗಳು", "logout": "ಲಾಗ್ ಔಟ್", "queue": "ಸರದಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "slots": "ಸ್ಲಾಟ್ ನಿರ್ವಹಣೆ", "analytics": "ವಿಶ್ಲೇಷಣೆ", "audit": "ಆಡಿಟ್ ದಾಖಲೆ", "login": "ಲಾಗಿನ್", "register": "ನೋಂದಣಿ", "toggle_theme": "ಡಾರ್ಕ್ ಮೋಡ್ ಅನ್ನು ಟಾಗಲ್ ಮಾಡಿ"},
        }
        language_options = [("en", "English"), ("hi", "हिन्दी"), ("kn", "ಕನ್ನಡ")]
        if current_user.is_authenticated and current_user.role == "farmer":
            from app.models import Centre
            active_booking = current_user.bookings.filter_by(status="booked").order_by("booked_at").first()
            help_centre = active_booking.centre if active_booking else Centre.query.filter_by(is_active=True).order_by(Centre.id.asc()).first()
            return {
                "unread_notification_count": current_user.notifications.filter_by(is_read=False).count(),
                "language": language,
                "labels": labels[language],
                "language_options": language_options,
                "farmer_help_centre": help_centre,
                "farmer_help_phone": app.config["FARMER_HELP_PHONE"],
                "farmer_help_email": app.config["FARMER_HELP_EMAIL"],
            }
        return {"unread_notification_count": 0, "language": language, "labels": labels[language], "language_options": language_options}

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("auth.post_login_redirect"))
        return redirect(url_for("public.home"))

    with app.app_context():
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            db.create_all()
            _upgrade_legacy_schema()
        from app.seed import seed_data
        seed_data()

    return app
