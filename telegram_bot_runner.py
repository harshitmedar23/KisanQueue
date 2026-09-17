"""
Run the Telegram bot worker as its own process, separate from the Flask
web server, so a slow/flaky Telegram connection never affects the site.

Usage (in a second terminal, venv activated, same folder as run.py):
    python telegram_bot_runner.py

Requires TELEGRAM_BOT_TOKEN to be set in .env (see .env.example).
"""
import logging

from app import create_app
from app.services.telegram_bot import run_polling

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    app = create_app()
    run_polling(app)
