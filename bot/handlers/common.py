import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import get_or_create_user, get_user
from keyboards import main_menu, language_select_kb
from strings import STRINGS, DEFAULT_LANG, get_lang
import database as db

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await get_or_create_user(user.id, user.username)

    # Check if language has been chosen
    lang_in_db = await db.get_user_language(user.id)
    if lang_in_db is None:
        # First time: show language picker
        s_de = STRINGS["de"]  # show picker text in DE by default
        await update.message.reply_text(
            s_de["lang_choose"],
            parse_mode="HTML",
            reply_markup=language_select_kb(),
        )
        return

    context.user_data["lang"] = lang_in_db
    s = STRINGS[lang_in_db]
    await update.message.reply_text(
        s["welcome"],
        parse_mode="HTML",
        reply_markup=main_menu(lang_in_db),
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the language picker inline keyboard."""
    lang = await get_lang(update.effective_user.id, context)
    s = STRINGS[lang]
    await update.message.reply_text(
        s["lang_choose"],
        parse_mode="HTML",
        reply_markup=language_select_kb(),
    )


async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle set_lang_en / set_lang_de inline button presses."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    chosen = "en" if query.data == "set_lang_en" else "de"
    await db.set_user_language(user_id, chosen)
    context.user_data["lang"] = chosen

    s = STRINGS[chosen]
    confirmation = s["lang_set_en"] if chosen == "en" else s["lang_set_de"]

    await query.message.reply_text(
        f"{confirmation}\n\n{s['welcome']}",
        parse_mode="HTML",
        reply_markup=main_menu(chosen),
    )


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    await update.message.reply_text(
        s["support"],
        parse_mode="HTML",
        reply_markup=main_menu(lang),
    )


async def my_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    client_tasks = await db.get_user_tasks_as_client(user_id)
    executor_tasks = await db.get_user_tasks_as_executor(user_id)

    active = [
        t for t in client_tasks + executor_tasks
        if t["status"] in ("in_progress", "dispute")
    ]

    if not active:
        await update.message.reply_text(
            s["my_chats_empty"],
            parse_mode="HTML",
            reply_markup=main_menu(lang),
        )
        return

    status_map = {
        "in_progress": s["status_in_progress"],
        "dispute":     s["status_dispute"],
    }

    await update.message.reply_text(
        s["my_chats_header"].format(n=len(active)) + "\n\n" + s["my_chats_hint"],
        parse_mode="HTML",
        reply_markup=main_menu(lang),
    )
    for t in active:
        role = s["role_client"] if t["client_id"] == user_id else s["role_executor"]
        status_label = status_map.get(t["status"], t["status"])
        await update.message.reply_text(
            f"🔗 Deal <code>#{t['task_id']}</code> — {t['title']}\n"
            f"{role} | {status_label}",
            parse_mode="HTML",
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await get_lang(update.effective_user.id, context)
    s = STRINGS[lang]
    await update.message.reply_text(
        s["unknown_cmd"],
        reply_markup=main_menu(lang),
    )


async def block_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if the user is blocked (should halt processing)."""
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if user and user.get("is_blocked"):
        lang = await get_lang(user_id, context)
        s = STRINGS[lang]
        await update.message.reply_text(s["account_blocked"])
        return True
    return False
