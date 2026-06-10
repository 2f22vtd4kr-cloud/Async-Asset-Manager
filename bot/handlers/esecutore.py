import json
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import TELEGRAM_CHANNEL_ID
from keyboards import main_menu, client_room_kb, executor_room_kb
from utils import format_task_summary
from strings import STRINGS, DEFAULT_LANG, get_lang
import database as db

logger = logging.getLogger(__name__)


async def area_esecutore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    user = await db.get_user(user_id)
    bal    = user["balance_usdt"] if user else 0.0
    tasks  = await db.get_user_tasks_as_executor(user_id)
    active    = [t for t in tasks if t["status"] == "in_progress"]
    completed = [t for t in tasks if t["status"] == "completed"]
    rating  = user["executor_rating"] if user else 5.0
    reviews = user["executor_reviews_count"] if user else 0

    text = (
        f"{s['exec_header']}\n\n"
        f"{s['balance_avail']}: <b>{bal:.2f} USDT</b>\n"
        f"{s['rating_line']}: <b>{rating:.1f}/5.0</b> ({reviews} {s['reviews_label']})\n\n"
        f"{s['exec_active']}: {len(active)}\n"
        f"{s['exec_completed']}: {len(completed)}\n\n"
        f"{s['exec_hint']}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(s["btn_channel"], url=f"https://t.me/c/{str(TELEGRAM_CHANNEL_ID).replace('-100', '')}")],
        [InlineKeyboardButton(s["btn_my_tasks"], callback_data="my_tasks_executor")],
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def claim_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    task_id = int(query.data.split("_", 1)[1])

    task = await db.get_task(task_id)
    if not task:
        await query.answer(s["exec_not_found"], show_alert=True)
        return
    if task["status"] != "open":
        await query.answer(s["exec_unavailable"], show_alert=True)
        return
    if task["client_id"] == user_id:
        await query.answer(s["exec_own_task"], show_alert=True)
        return

    executor = await db.get_or_create_user(user_id)
    if executor.get("is_shadow_banned"):
        await query.answer(s["exec_shadow_ban"], show_alert=True)
        return

    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] != "open":
            await query.answer(s["exec_taken"], show_alert=True)
            return
        await conn.execute("BEGIN")
        await conn.execute(
            "UPDATE tasks SET status = 'in_progress', executor_id = ?, claimed_at = CURRENT_TIMESTAMP WHERE task_id = ? AND status = 'open'",
            (user_id, task_id),
        )
        await conn.execute("COMMIT")

    task = await db.get_task(task_id)
    if task and task.get("channel_message_id"):
        try:
            await update.get_bot().edit_message_text(
                chat_id=TELEGRAM_CHANNEL_ID,
                message_id=task["channel_message_id"],
                text=(
                    f"📋 <b>{task['title']}</b>\n\n"
                    f"{s['channel_in_progress']}\n"
                    f"💰 {task['reward_gross']:.2f} USDT\n"
                    f"{s['summary_id']}: <code>{task_id}</code>"
                ),
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception as e:
            logger.warning(s["exec_cannot_update_channel"] if "exec_cannot_update_channel" in s else "Channel update failed: %s", e)

    import uuid
    room_token = uuid.uuid4().hex
    await db.create_deal_session(task_id, task["client_id"], user_id, room_token)

    bot = update.get_bot()

    # Notify client in their language
    client_lang = await db.get_user_language(task["client_id"]) or DEFAULT_LANG
    cs = STRINGS[client_lang]
    try:
        await bot.send_message(
            chat_id=task["client_id"],
            text=cs["exec_client_msg"].format(id=task_id, title=task["title"]),
            parse_mode="HTML",
            reply_markup=client_room_kb(task_id, client_lang),
        )
    except Exception as e:
        logger.error("Could not notify client: %s", e)

    await query.message.reply_text(
        s["exec_executor_msg"].format(id=task_id, title=task["title"], net=task["reward_net"]),
        parse_mode="HTML",
        reply_markup=executor_room_kb(task_id, lang),
    )


async def my_tasks_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    tasks = await db.get_user_tasks_as_executor(user_id)
    if not tasks:
        await query.message.reply_text(s["exec_no_tasks"])
        return
    for t in tasks[:10]:
        await query.message.reply_text(format_task_summary(t, lang), parse_mode="HTML")
