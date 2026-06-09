import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import get_or_create_user, get_user
from keyboards import MAIN_MENU
from utils import format_task_summary, STATUS_LABELS
import database as db

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🐸 <b>Benvenuto su Fai un Salto!</b>\n\n"
    "La piattaforma P2P per studenti universitari italiani.\n"
    "Pubblica incarichi, trova collaboratori e gestisci i pagamenti in modo sicuro.\n\n"
    "Seleziona un'opzione dal menu qui sotto:"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await get_or_create_user(user.id, user.username)
    await update.message.reply_text(WELCOME_TEXT, parse_mode="HTML", reply_markup=MAIN_MENU)


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ <b>Supporto Fai un Salto</b>\n\n"
        "Per assistenza contatta il nostro team:\n"
        "• Disputa in corso? Usa il pulsante 🚨 nella chat del deal.\n"
        "• Problemi tecnici? Scrivi a @FaiUnSaltoSupport\n"
        "• Commissioni: 10% su ogni incarico completato.\n"
        "• Conversione Stars → USDT: 1 Star = 0.02 USDT"
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
            "📂 <b>I Miei Chat Attivi</b>\n\nNessuna chat attiva al momento.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return

    await update.message.reply_text(
        f"📂 <b>I Miei Chat Attivi</b> ({len(active)} deal)\n\n"
        "Scrivi un messaggio in qualsiasi chat attiva: verrà inoltrato automaticamente all'altra parte.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )
    for t in active:
        role = "Committente" if t["client_id"] == user_id else "Esecutore"
        await update.message.reply_text(
            f"🔗 Deal <code>#{t['task_id']}</code> — {t['title']}\n"
            f"Ruolo: {role} | Stato: {STATUS_LABELS.get(t['status'], t['status'])}",
            parse_mode="HTML",
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ Comando non riconosciuto. Usa il menu qui sotto.",
        reply_markup=MAIN_MENU,
    )


async def block_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if the user is blocked (should halt processing)."""
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if user and user.get("is_blocked"):
        await update.message.reply_text("🚫 Il tuo account è stato sospeso.")
        return True
    return False
