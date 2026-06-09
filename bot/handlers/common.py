import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import get_or_create_user, get_user
from keyboards import MAIN_MENU
from utils import format_task_summary, STATUS_LABELS
import database as db

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🐸 <b>Willkommen bei Fai un Salto!</b>\n\n"
    "Die P2P-Plattform für deutsche Studierende.\n"
    "Veröffentliche Aufträge, finde Mitarbeiter und wickle Zahlungen sicher ab.\n\n"
    "Wähle eine Option aus dem Menü unten:"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await get_or_create_user(user.id, user.username)
    await update.message.reply_text(WELCOME_TEXT, parse_mode="HTML", reply_markup=MAIN_MENU)


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ <b>Support – Fai un Salto</b>\n\n"
        "Für Hilfe kontaktiere unser Team:\n"
        "• Streitfall? Nutze den 🚨-Button im Deal-Chat.\n"
        "• Technische Probleme? Schreibe an @FaiUnSaltoSupport\n"
        "• Gebühren: 10% auf jeden abgeschlossenen Auftrag.\n"
        "• Umrechnung Stars → USDT: 1 Star = 0,02 USDT"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)


async def my_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    client_tasks = await db.get_user_tasks_as_client(user_id)
    executor_tasks = await db.get_user_tasks_as_executor(user_id)

    active = [
        t for t in client_tasks + executor_tasks
        if t["status"] in ("in_progress", "dispute")
    ]

    if not active:
        await update.message.reply_text(
            "📂 <b>Meine aktiven Chats</b>\n\nDerzeit keine aktiven Chats.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return

    await update.message.reply_text(
        f"📂 <b>Meine aktiven Chats</b> ({len(active)} Deals)\n\n"
        "Schreibe in einen aktiven Chat: die Nachricht wird automatisch anonym weitergeleitet.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )
    for t in active:
        role = "Auftraggeber" if t["client_id"] == user_id else "Auftragnehmer"
        await update.message.reply_text(
            f"🔗 Deal <code>#{t['task_id']}</code> — {t['title']}\n"
            f"Rolle: {role} | Status: {STATUS_LABELS.get(t['status'], t['status'])}",
            parse_mode="HTML",
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ Unbekannter Befehl. Nutze das Menü unten.",
        reply_markup=MAIN_MENU,
    )


async def block_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if the user is blocked (should halt processing)."""
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if user and user.get("is_blocked"):
        await update.message.reply_text("🚫 Dein Konto wurde gesperrt.")
        return True
    return False
