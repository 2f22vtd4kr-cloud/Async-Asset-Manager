import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_TG_ID
from keyboards import main_menu, admin_dispute_kb
from strings import STRINGS, DEFAULT_LANG
import database as db

logger = logging.getLogger(__name__)


async def open_dispute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    task_id = int(query.data.split("_", 1)[1])

    task = await db.get_task(task_id)
    if not task:
        await query.answer(STRINGS[DEFAULT_LANG]["admin_not_found"], show_alert=True)
        return

    session = await db.get_session_by_task(task_id)
    if not session:
        await query.answer(STRINGS[DEFAULT_LANG]["admin_session_not_found"], show_alert=True)
        return

    if user_id not in (session["client_id"], session["executor_id"]):
        await query.answer(STRINGS[DEFAULT_LANG]["admin_not_auth"], show_alert=True)
        return

    if session["status"] != "active":
        await query.answer(STRINGS[DEFAULT_LANG]["admin_already_open"], show_alert=True)
        return

    await db.close_deal_session(task_id, "disputed")

    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE tasks SET status = 'dispute', disputed_at = CURRENT_TIMESTAMP WHERE task_id = ?",
            (task_id,),
        )
        await conn.execute(
            "UPDATE users SET disputes_initiated = disputes_initiated + 1 WHERE telegram_id = ?",
            (user_id,),
        )
        await conn.commit()

    # Admin audit (always in German for admin convenience)
    s = STRINGS["de"]
    messages = await db.get_deal_messages(task_id)
    msg_summary = ""
    for m in messages[-20:]:
        role = s["admin_role_client"] if m["sender_id"] == task["client_id"] else s["admin_role_executor"]
        msg_summary += f"[{role}] {m['message_type']}: {m['content_preview'][:80]}\n"

    audit_text = (
        f"{s['admin_dispute_hdr']}\n\n"
        f"🆔 Auftrag #{task_id} — {task['title']}\n"
        f"{s['admin_client_label']}: <code>{task['client_id']}</code>\n"
        f"{s['admin_executor_label']}: <code>{task['executor_id']}</code>\n"
        f"{s['admin_escrow_label']}: <b>{task['reward_gross']:.2f} USDT</b>\n"
        f"{s['admin_audit_category']}: {task.get('category', s['na'])}\n"
        f"{s['admin_audit_description']}: {task.get('description', '')[:200]}\n\n"
        f"{s['admin_last_msgs']}\n<pre>{msg_summary[:1000]}</pre>"
    )
    bot = context.bot
    try:
        await bot.send_message(
            chat_id=ADMIN_TG_ID,
            text=audit_text,
            parse_mode="HTML",
            reply_markup=admin_dispute_kb(task_id),
        )
    except Exception as e:
        logger.error("Could not send audit to admin: %s", e)

    # Notify parties in their respective languages
    for party_id in (task["client_id"], task["executor_id"]):
        party_lang = await db.get_user_language(party_id) or DEFAULT_LANG
        ps = STRINGS[party_lang]
        try:
            await bot.send_message(
                chat_id=party_id,
                text=ps["admin_dispute_notify"].format(id=task_id),
                parse_mode="HTML",
                reply_markup=main_menu(party_lang),
            )
        except Exception as e:
            logger.warning("Could not notify party %s: %s", party_id, e)


async def admin_release_executor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TG_ID:
        await query.answer(STRINGS[DEFAULT_LANG]["admin_not_auth"], show_alert=True)
        return

    task_id = int(query.data.split("_", 2)[2])
    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text(STRINGS[DEFAULT_LANG]["admin_not_found"])
        return

    ok = await db.release_to_executor(task_id)
    if not ok:
        await query.message.reply_text(STRINGS[DEFAULT_LANG]["admin_release_err"])
        return

    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE users SET disputes_lost = disputes_lost + 1 WHERE telegram_id = ?",
            (task["client_id"],),
        )
        await conn.commit()
    await db.flag_user_if_needed(task["client_id"])

    task = await db.get_task(task_id)
    bot  = context.bot

    for party_id, key, fmt_kwargs in [
        (task["client_id"],   "admin_release_client",   {"id": task_id}),
        (task["executor_id"], "admin_release_executor",  {"id": task_id, "net": task["reward_net"]}),
    ]:
        party_lang = await db.get_user_language(party_id) or DEFAULT_LANG
        ps = STRINGS[party_lang]
        try:
            await bot.send_message(chat_id=party_id, text=ps[key].format(**fmt_kwargs), reply_markup=main_menu(party_lang))
        except Exception:
            pass

    from handlers.rating import prompt_ratings
    await prompt_ratings(bot, task_id, task["client_id"], task["executor_id"])

    await query.message.edit_text(
        query.message.text + f"\n\n{STRINGS['de']['admin_release_resolved']}",
        parse_mode="HTML",
    )


async def admin_refund_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TG_ID:
        await query.answer(STRINGS[DEFAULT_LANG]["admin_not_auth"], show_alert=True)
        return

    task_id = int(query.data.split("_", 2)[2])
    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text(STRINGS[DEFAULT_LANG]["admin_not_found"])
        return

    ok = await db.refund_client(task_id)
    if not ok:
        await query.message.reply_text(STRINGS[DEFAULT_LANG]["admin_refund_err"])
        return

    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE users SET disputes_lost = disputes_lost + 1 WHERE telegram_id = ?",
            (task["executor_id"],),
        )
        await conn.commit()
    await db.flag_user_if_needed(task["executor_id"])

    task = await db.get_task(task_id)
    bot  = context.bot

    for party_id, key, fmt_kwargs in [
        (task["client_id"],   "admin_refund_client",   {"id": task_id, "gross": task["reward_gross"]}),
        (task["executor_id"], "admin_refund_executor",  {"id": task_id}),
    ]:
        party_lang = await db.get_user_language(party_id) or DEFAULT_LANG
        ps = STRINGS[party_lang]
        try:
            await bot.send_message(chat_id=party_id, text=ps[key].format(**fmt_kwargs), reply_markup=main_menu(party_lang))
        except Exception:
            pass

    from handlers.rating import prompt_ratings
    await prompt_ratings(bot, task_id, task["client_id"], task["executor_id"])

    await query.message.edit_text(
        query.message.text + f"\n\n{STRINGS['de']['admin_refund_resolved']}",
        parse_mode="HTML",
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_TG_ID:
        return

    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*) FROM users") as c:
            users_count = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*), status FROM tasks GROUP BY status") as c:
            task_stats = await c.fetchall()
        async with conn.execute("SELECT total_collected_fees FROM admin_revenue WHERE id=1") as c:
            fees_row = await c.fetchone()

    fees = fees_row[0] if fees_row else 0.0
    task_lines = "\n".join(f"  {s}: {n}" for n, s in task_stats)
    sd = STRINGS["de"]
    await update.message.reply_text(
        f"{sd['admin_stats_hdr']}\n\n"
        f"{sd['admin_stats_users']}: {users_count}\n"
        f"{sd['admin_stats_tasks']}:\n{task_lines}\n"
        f"{sd['admin_stats_fees']}: <b>{fees:.4f} USDT</b>",
        parse_mode="HTML",
    )
