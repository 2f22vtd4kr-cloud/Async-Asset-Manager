import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".jar"}


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        level=logging.INFO,
    )


def is_blocked_file(file_name: str) -> bool:
    _, ext = (file_name.rsplit(".", 1) if "." in file_name else (file_name, ""))
    return f".{ext.lower()}" in BLOCKED_EXTENSIONS


def validate_reward(text: str) -> Optional[float]:
    text = text.strip().replace(",", ".")
    try:
        value = float(text)
        if value <= 0 or value > 10_000:
            return None
        return round(value, 2)
    except ValueError:
        return None


def calc_net_reward(gross: float, fee_rate: float = 0.10) -> float:
    return round(gross * (1 - fee_rate), 8)


def calc_stars_for_usdt(usdt_amount: float, rate: float = 0.02) -> int:
    return max(1, int(usdt_amount / rate))


def format_task_summary(task: dict, lang: str = "de") -> str:
    from strings import STRINGS, DEFAULT_LANG
    s = STRINGS.get(lang, STRINGS[DEFAULT_LANG])

    status_map = {
        "open":        s["status_open"],
        "in_progress": s["status_in_progress"],
        "completed":   s["status_completed"],
        "dispute":     s["status_dispute"],
        "cancelled":   s["status_cancelled"],
    }
    status_label = status_map.get(task.get("status", ""), task.get("status", ""))
    na = s["na"]

    lines = [
        f"📋 <b>{task['title']}</b>",
        f"{s['summary_category']}: {task.get('category', s['cat_general'])}",
        f"{s['summary_deadline']}: {task.get('deadline', na)}",
        f"{s['summary_gross']}: <b>{task['reward_gross']:.2f} USDT</b>",
        f"{s['summary_net']}: <b>{task['reward_net']:.2f} USDT</b>",
        f"{s['summary_status']}: {status_label}",
        f"{s['summary_id']}: <code>{task['task_id']}</code>",
    ]
    if task.get("description"):
        lines.insert(1, f"📝 {task['description']}")
    return "\n".join(lines)


def strip_username_mentions(text: str) -> str:
    return re.sub(r"@\w+", "[?]", text)
