"""
Post-completion rating system.

After a deal closes (completion or dispute resolution) both parties
are prompted to leave a 1–5 star review for each other.
Ratings update a weighted running average stored in users.client_rating
and users.executor_rating.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from keyboards import MAIN_MENU
import database as db

logger = logging.getLogger(__name__)

STAR_LABELS = {1: "😞 Sehr schlecht", 2: "😐 Schlecht", 3: "🙂 Ausreichend", 4: "😊 Gut", 5: "🌟 Ausgezeichnet"}


async def rate_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Client rates the executor: callback data = rate_exec_{task_id}_{stars}"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    parts = query.data.split("_")
    task_id = int(parts[2])
    stars = int(parts[3])

    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text("❌ Auftrag nicht gefunden.")
        return

    if task["client_id"] != user_id:
        await query.answer("❌ Nur der Auftraggeber kann den Auftragnehmer bewerten.", show_alert=True)
        return

    if not task.get("executor_id"):
        await query.message.reply_text("❌ Kein Auftragnehmer zu bewerten.")
        return

    await db.update_rating(task["executor_id"], "executor", stars)
    label = STAR_LABELS.get(stars, "")

    await query.message.edit_text(
        f"⭐ Du hast den Auftragnehmer mit <b>{'⭐' * stars}</b> bewertet — {label}\nDanke für dein Feedback!",
        parse_mode="HTML",
    )


async def rate_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executor rates the client: callback data = rate_client_{task_id}_{stars}"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    parts = query.data.split("_")
    task_id = int(parts[2])
    stars = int(parts[3])

    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text("❌ Auftrag nicht gefunden.")
        return

    if task["executor_id"] != user_id:
        await query.answer("❌ Nur der Auftragnehmer kann den Auftraggeber bewerten.", show_alert=True)
        return

    await db.update_rating(task["client_id"], "client", stars)
    label = STAR_LABELS.get(stars, "")

    await query.message.edit_text(
        f"⭐ Du hast den Auftraggeber mit <b>{'⭐' * stars}</b> bewertet — {label}\nDanke für dein Feedback!",
        parse_mode="HTML",
    )


async def prompt_ratings(bot, task_id: int, client_id: int, executor_id: int) -> None:
    """Send rating prompts to both parties after a deal closes."""
    from keyboards import rating_kb

    try:
        await bot.send_message(
            chat_id=client_id,
            text="⭐ <b>Wie lief der Deal?</b>\nBewerte den Auftragnehmer:",
            parse_mode="HTML",
            reply_markup=rating_kb(task_id, "exec"),
        )
    except Exception as e:
        logger.warning("Bewertungsaufforderung an Auftraggeber konnte nicht gesendet werden: %s", e)

    try:
        await bot.send_message(
            chat_id=executor_id,
            text="⭐ <b>Wie lief der Deal?</b>\nBewerte den Auftraggeber:",
            parse_mode="HTML",
            reply_markup=rating_kb(task_id, "client"),
        )
    except Exception as e:
        logger.warning("Bewertungsaufforderung an Auftragnehmer konnte nicht gesendet werden: %s", e)
