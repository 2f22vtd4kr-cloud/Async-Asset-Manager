"""
Post-completion rating system.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from keyboards import main_menu, rating_kb
from strings import STRINGS, DEFAULT_LANG, get_lang
import database as db

logger = logging.getLogger(__name__)


async def rate_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang    = await get_lang(user_id, context)
    s       = STRINGS[lang]

    parts   = query.data.split("_")
    task_id = int(parts[2])
    stars   = int(parts[3])

    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text(s["rating_not_found"])
        return
    if task["client_id"] != user_id:
        await query.answer(s["rating_only_client"], show_alert=True)
        return
    if not task.get("executor_id"):
        await query.message.reply_text(s["rating_no_executor"])
        return

    await db.update_rating(task["executor_id"], "executor", stars)
    label = s["rating_labels"].get(stars, "")
    await query.message.edit_text(
        s["rated_exec"].format(stars="⭐" * stars, label=label),
        parse_mode="HTML",
    )


async def rate_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang    = await get_lang(user_id, context)
    s       = STRINGS[lang]

    parts   = query.data.split("_")
    task_id = int(parts[2])
    stars   = int(parts[3])

    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text(s["rating_not_found"])
        return
    if task["executor_id"] != user_id:
        await query.answer(s["rating_only_executor"], show_alert=True)
        return

    await db.update_rating(task["client_id"], "client", stars)
    label = s["rating_labels"].get(stars, "")
    await query.message.edit_text(
        s["rated_client"].format(stars="⭐" * stars, label=label),
        parse_mode="HTML",
    )


async def prompt_ratings(bot, task_id: int, client_id: int, executor_id: int) -> None:
    """Send rating prompts to both parties in their own language."""
    client_lang   = await db.get_user_language(client_id)   or DEFAULT_LANG
    executor_lang = await db.get_user_language(executor_id) or DEFAULT_LANG

    cs = STRINGS[client_lang]
    es = STRINGS[executor_lang]

    try:
        await bot.send_message(
            chat_id=client_id,
            text=cs["rate_exec_prompt"],
            parse_mode="HTML",
            reply_markup=rating_kb(task_id, "exec"),
        )
    except Exception as e:
        logger.warning("Could not send rating prompt to client: %s", e)

    try:
        await bot.send_message(
            chat_id=executor_id,
            text=es["rate_client_prompt"],
            parse_mode="HTML",
            reply_markup=rating_kb(task_id, "client"),
        )
    except Exception as e:
        logger.warning("Could not send rating prompt to executor: %s", e)
