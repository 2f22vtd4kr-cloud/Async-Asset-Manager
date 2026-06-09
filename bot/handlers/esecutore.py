import json
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import TELEGRAM_CHANNEL_ID
from keyboards import MAIN_MENU, executor_room_kb
from utils import format_task_summary, STATUS_LABELS
import database as db

logger = logging.getLogger(__name__)


async def area_esecutore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0
    tasks = await db.get_user_tasks_as_executor(user_id)
    active = [t for t in tasks if t["status"] == "in_progress"]
    completed = [t for t in tasks if t["status"] == "completed"]
    rating = user["executor_rating"] if user else 5.0
    reviews = user["executor_reviews_count"] if user else 0

    text = (
        "🛠️ <b>Area Esecutore</b>\n\n"
        f"💰 Saldo disponibile: <b>{bal:.2f} USDT</b>\n"
        f"⭐ Rating: <b>{rating:.1f}/5.0</b> ({reviews} recensioni)\n\n"
        f"⚙️ Incarichi attivi: {len(active)}\n"
        f"✅ Completati: {len(completed)}\n\n"
        "Visita il canale per trovare nuovi incarichi disponibili."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Vai al Canale Incarichi", url=f"https://t.me/c/{str(TELEGRAM_CHANNEL_ID).replace('-100', '')}")],
        [InlineKeyboardButton("📋 I Miei Incarichi", callback_data="my_tasks_executor")],
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def claim_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the inline button click from the channel post."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    task_id = int(query.data.split("_", 1)[1])

    task = await db.get_task(task_id)
    if not task:
        await query.answer("❌ Incarico non trovato.", show_alert=True)
        return

    if task["status"] != "open":
        await query.answer("🔴 Questo incarico non è più disponibile.", show_alert=True)
        return

    if task["client_id"] == user_id:
        await query.answer("⚠️ Non puoi prendere il tuo stesso incarico.", show_alert=True)
        return

    # Check if user is shadow-banned
    executor = await db.get_or_create_user(user_id)
    if executor.get("is_shadow_banned"):
        await query.answer("🚫 Operazione non disponibile.", show_alert=True)
        return

    # Atomically mark as in_progress
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] != "open":
            await query.answer("🔴 Incarico già preso.", show_alert=True)
            return
        await conn.execute("BEGIN")
        await conn.execute(
            "UPDATE tasks SET status = 'in_progress', executor_id = ?, claimed_at = CURRENT_TIMESTAMP WHERE task_id = ? AND status = 'open'",
            (user_id, task_id),
        )
        await conn.execute("COMMIT")

    # Update channel message: remove inline buttons, update caption
    task = await db.get_task(task_id)
    if task and task.get("channel_message_id"):
        try:
            await update.get_bot().edit_message_text(
                chat_id=TELEGRAM_CHANNEL_ID,
                message_id=task["channel_message_id"],
                text=(
                    f"📋 <b>{task['title']}</b> #PostProtetto\n\n"
                    f"🔴 <b>In corso</b> — Incarico assegnato\n"
                    f"💰 Compenso: {task['reward_gross']:.2f} USDT\n"
                    f"🆔 Task #{task_id}"
                ),
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception as e:
            logger.warning("Impossibile aggiornare il messaggio canale: %s", e)

    # Create deal session
    import uuid
    room_token = uuid.uuid4().hex
    await db.create_deal_session(task_id, task["client_id"], user_id, room_token)

    # Notify both parties
    bot = update.get_bot()
    notify_client = (
        f"🤝 <b>Incarico accettato!</b>\n\n"
        f"Task #{task_id} — {task['title']}\n"
        "Un esecutore ha accettato il tuo incarico. La chat è ora attiva.\n"
        "Scrivi qui per comunicare in modo anonimo."
    )
    notify_executor = (
        f"✅ <b>Hai preso l'incarico!</b>\n\n"
        f"Task #{task_id} — {task['title']}\n"
        f"💰 Compenso netto: <b>{task['reward_net']:.2f} USDT</b>\n"
        "Scrivi qui per comunicare con il committente in modo anonimo."
    )

    from keyboards import client_room_kb, executor_room_kb
    try:
        await bot.send_message(
            chat_id=task["client_id"],
            text=notify_client,
            parse_mode="HTML",
            reply_markup=client_room_kb(task_id),
        )
    except Exception as e:
        logger.error("Impossibile notificare committente: %s", e)

    await query.message.reply_text(
        notify_executor, parse_mode="HTML", reply_markup=executor_room_kb(task_id)
    )


async def my_tasks_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = await db.get_user_tasks_as_executor(user_id)
    if not tasks:
        await query.message.reply_text("📋 Nessun incarico preso finora.")
        return
    for t in tasks[:10]:
        await query.message.reply_text(format_task_summary(t), parse_mode="HTML")
