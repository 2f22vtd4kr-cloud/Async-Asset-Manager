import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_TG_ID
from keyboards import MAIN_MENU, admin_dispute_kb
import database as db

logger = logging.getLogger(__name__)


async def open_dispute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    task_id = int(query.data.split("_", 1)[1])

    task = await db.get_task(task_id)
    if not task:
        await query.answer("❌ Auftrag nicht gefunden.", show_alert=True)
        return

    session = await db.get_session_by_task(task_id)
    if not session:
        await query.answer("❌ Sitzung nicht gefunden.", show_alert=True)
        return

    if user_id not in (session["client_id"], session["executor_id"]):
        await query.answer("❌ Nicht autorisiert.", show_alert=True)
        return

    if session["status"] != "active":
        await query.answer("⚠️ Der Streitfall wurde bereits eröffnet.", show_alert=True)
        return

    # 1. Tear down session → disputed
    await db.close_deal_session(task_id, "disputed")

    # 2. Update task status
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

    # 3. Compile audit package
    messages = await db.get_deal_messages(task_id)
    msg_summary = ""
    for m in messages[-20:]:  # Last 20 messages
        role = "AG" if m["sender_id"] == task["client_id"] else "AN"
        msg_summary += f"[{role}] {m['message_type']}: {m['content_preview'][:80]}\n"

    audit_text = (
        f"🚨 <b>STREITFALL ERÖFFNET</b>\n\n"
        f"🆔 Auftrag #{task_id} — {task['title']}\n"
        f"👤 Auftraggeber: <code>{task['client_id']}</code>\n"
        f"🛠 Auftragnehmer: <code>{task['executor_id']}</code>\n"
        f"💰 Treuhandbetrag: <b>{task['reward_gross']:.2f} USDT</b>\n"
        f"📅 Kategorie: {task.get('category', 'k.A.')}\n"
        f"📋 Beschreibung: {task.get('description', '')[:200]}\n\n"
        f"<b>Letzte Nachrichten:</b>\n<pre>{msg_summary[:1000]}</pre>"
    )

    # 4. Route to admin
    bot = context.bot
    try:
        await bot.send_message(
            chat_id=ADMIN_TG_ID,
            text=audit_text,
            parse_mode="HTML",
            reply_markup=admin_dispute_kb(task_id),
        )
    except Exception as e:
        logger.error("Audit konnte nicht an Admin gesendet werden: %s", e)

    # Notify both parties
    for party_id in (task["client_id"], task["executor_id"]):
        try:
            await bot.send_message(
                chat_id=party_id,
                text=(
                    f"🚨 <b>Streitfall für Auftrag #{task_id} eröffnet</b>\n\n"
                    "Unser Team wird den Fall prüfen und die Entscheidung mitteilen.\n"
                    "Der Chat wurde pausiert."
                ),
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
        except Exception as e:
            logger.warning("Partei %s konnte nicht benachrichtigt werden: %s", party_id, e)


async def admin_release_executor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: release 90% to executor, 10% to platform."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TG_ID:
        await query.answer("🚫 Nicht autorisiert.", show_alert=True)
        return

    task_id = int(query.data.split("_", 2)[2])
    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text("❌ Auftrag nicht gefunden.")
        return

    ok = await db.release_to_executor(task_id)
    if not ok:
        await query.message.reply_text("❌ Fehler bei der Freigabe der Mittel.")
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
    bot = context.bot
    for party_id, msg in [
        (task["client_id"], f"⚖️ Streitfall Auftrag #{task_id}: Die Mittel wurden dem Auftragnehmer zugesprochen."),
        (task["executor_id"], f"🟢 Streitfall Auftrag #{task_id}: Du hast die Vergütung von {task['reward_net']:.2f} USDT erhalten."),
    ]:
        try:
            await bot.send_message(chat_id=party_id, text=msg, reply_markup=MAIN_MENU)
        except Exception:
            pass

    from handlers.rating import prompt_ratings
    await prompt_ratings(bot, task_id, task["client_id"], task["executor_id"])

    await query.message.edit_text(
        query.message.text + f"\n\n✅ <b>Gelöst: Mittel an Auftragnehmer freigegeben.</b>",
        parse_mode="HTML",
    )


async def admin_refund_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: full refund to client."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TG_ID:
        await query.answer("🚫 Nicht autorisiert.", show_alert=True)
        return

    task_id = int(query.data.split("_", 2)[2])
    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text("❌ Auftrag nicht gefunden.")
        return

    ok = await db.refund_client(task_id)
    if not ok:
        await query.message.reply_text("❌ Fehler bei der Rückerstattung.")
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
    bot = context.bot
    for party_id, msg in [
        (task["client_id"], f"🔴 Streitfall Auftrag #{task_id}: Rückerstattung abgeschlossen. {task['reward_gross']:.2f} USDT deinem Guthaben gutgeschrieben."),
        (task["executor_id"], f"⚖️ Streitfall Auftrag #{task_id}: Die Mittel wurden dem Auftraggeber zurückerstattet."),
    ]:
        try:
            await bot.send_message(chat_id=party_id, text=msg, reply_markup=MAIN_MENU)
        except Exception:
            pass

    from handlers.rating import prompt_ratings
    await prompt_ratings(bot, task_id, task["client_id"], task["executor_id"])

    await query.message.edit_text(
        query.message.text + f"\n\n🔴 <b>Gelöst: Auftraggeber erstattet.</b>",
        parse_mode="HTML",
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only stats command."""
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

    await update.message.reply_text(
        f"📊 <b>Admin-Statistiken</b>\n\n"
        f"👥 Registrierte Nutzer: {users_count}\n"
        f"📋 Aufträge nach Status:\n{task_lines}\n"
        f"💰 Gesamtgebühren: <b>{fees:.4f} USDT</b>",
        parse_mode="HTML",
    )
