import os

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
TELEGRAM_CHANNEL_ID: int = int(os.environ["TELEGRAM_CHANNEL_ID"])
ADMIN_TG_ID: int = int(os.environ["ADMIN_TG_ID"])
CRYPTOBOT_TOKEN: str = os.environ["CRYPTOBOT_TOKEN"]

STAR_TO_USDT_RATE: float = 0.02
PLATFORM_FEE_RATE: float = 0.10
MINI_APP_URL: str = os.environ.get("MINI_APP_URL", "https://example.com/mini_app.html")
