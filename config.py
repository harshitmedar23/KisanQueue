import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


def _bool(name, default="False"):
    return os.environ.get(name, default).strip().lower() in ("true", "1", "yes")


def _database_url():
    url = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'farmer_procurement.db')}"
    )
    return url.replace("mysql://", "mysql+pymysql://", 1) if url.startswith("mysql://") else url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai").strip().lower()
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or None
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or None
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MIGRATION_DIRECTORY = os.path.join(basedir, "migrations")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = "200 per day;50 per hour"

    # --- Email (Flask-Mail) ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or None
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    # When True (default), Flask-Mail won't actually send anything -- messages are
    # just logged. Set to False and supply real credentials to send real email.
    MAIL_SUPPRESS_SEND = _bool("MAIL_SUPPRESS_SEND", "True")

    # --- Web Push (VAPID / pywebpush) ---
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY") or None
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY") or None
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")

    # --- SMS (Twilio) - disabled by default per spec ---
    SMS_ENABLED = _bool("SMS_ENABLED", "False")
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID") or None
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") or None
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER") or None
    TWILIO_CONTENT_SID = os.environ.get("TWILIO_CONTENT_SID") or None

    # --- Telegram Bot ---
    # Get this from @BotFather on Telegram. Enabled automatically once a token is set.
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or None
    TELEGRAM_ENABLED = _bool("TELEGRAM_ENABLED", "True") and bool(TELEGRAM_BOT_TOKEN)
    TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME") or None

    # --- Real-time ---
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "threading")

    # --- OTP ---
    OTP_EXPIRY_MINUTES = 5
    # Demo mode: instead of actually sending an SMS (no gateway configured),
    # the OTP is shown directly to the user via a flash message / API response.
    OTP_DEMO_MODE = _bool("OTP_DEMO_MODE", "True")

    # --- Queue ---
    AVG_MINUTES_PER_TOKEN = 5
    MSP_DEFAULT_CROP = "Wheat"
    UPI_VPA = os.environ.get("UPI_VPA", "farmerprocurement@upi")
    UPI_PAYEE_NAME = os.environ.get("UPI_PAYEE_NAME", "Farmer Procurement")
    FARMER_HELP_PHONE = os.environ.get("FARMER_HELP_PHONE", "1800-123-4567")
    FARMER_HELP_EMAIL = os.environ.get("FARMER_HELP_EMAIL", "help@farmerprocurement.local")

    # Optional government/market price API. The app keeps database prices when
    # these values are not configured or the upstream service is unavailable.
    MANDI_API_URL = os.environ.get("MANDI_API_URL") or None
    MANDI_API_KEY = os.environ.get("MANDI_API_KEY") or None
    MANDI_API_LIMIT = int(os.environ.get("MANDI_API_LIMIT", "100"))
    MANDI_API_CROP_FIELD = os.environ.get("MANDI_API_CROP_FIELD", "commodity")
    MANDI_API_MARKET_FIELD = os.environ.get("MANDI_API_MARKET_FIELD", "market")
    MANDI_API_PRICE_FIELD = os.environ.get("MANDI_API_PRICE_FIELD", "modal_price")
    MANDI_API_SYNC_INTERVAL_SECONDS = int(os.environ.get("MANDI_API_SYNC_INTERVAL_SECONDS", "900"))
    MANDI_API_TIMEOUT_SECONDS = int(os.environ.get("MANDI_API_TIMEOUT_SECONDS", "2"))
    VOICE_MAX_AUDIO_BYTES = int(os.environ.get("VOICE_MAX_AUDIO_BYTES", str(10 * 1024 * 1024)))
