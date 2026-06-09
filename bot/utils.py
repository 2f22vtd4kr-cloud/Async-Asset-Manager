import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".jar"}

STATUS_LABELS = {
    "open": "🟢 Offen",
    "in_progress": "🟡 In Bearbeitung",
    "completed": "✅ Abgeschlossen",
    "dispute": "🔴 Streitfall",
    "cancelled": "❌ Storniert",
}


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        level=logging.INFO,
    )


def is_blocked_file(file_name: str) -> bool:
    """Return True if the filename has a dangerous extension."""
    _, ext = (file_name.rsplit(".", 1) if "." in file_name else (file_name, ""))
    return f".{ext.lower()}" in BLOCKED_EXTENSIONS


def validate_reward(text: str) -> Optional[float]:
    """Parse and validate a USDT reward amount. Returns float or None."""
    text = text.strip().replace(",", ".")
    try:
        value = float(text)
        if value <= 0:
            return None
        # Max safety cap: 10,000 USDT
        if value > 10_000:
            return None
        return round(value, 2)
    except ValueError:
        return None


def calc_net_reward(gross: float, fee_rate: float = 0.10) -> float:
    """Return executor's net reward after platform fee."""
    return round(gross * (1 - fee_rate), 8)


def calc_stars_for_usdt(usdt_amount: float, rate: float = 0.02) -> int:
    """Return number of Telegram Stars needed to top up `usdt_amount` USDT."""
    return max(1, int(usdt_amount / rate))


def format_task_summary(task: dict) -> str:
    status_label = STATUS_LABELS.get(task.get("status", ""), task.get("status", ""))
    lines = [
        f"📋 <b>{task['title']}</b>",
        f"🏷 Kategorie: {task.get('category', 'Allgemein')}",
        f"📅 Frist: {task.get('deadline', 'k.A.')}",
        f"💰 Bruttovergütung: <b>{task['reward_gross']:.2f} USDT</b>",
        f"💵 Netto Auftragnehmer: <b>{task['reward_net']:.2f} USDT</b>",
        f"🔖 Status: {status_label}",
        f"🆔 Auftrags-ID: <code>{task['task_id']}</code>",
    ]
    if task.get("description"):
        lines.insert(1, f"📝 {task['description']}")
    return "\n".join(lines)


def strip_username_mentions(text: str) -> str:
    """Remove @username mentions to protect privacy."""
    return re.sub(r"@\w+", "[Nutzer]", text)
