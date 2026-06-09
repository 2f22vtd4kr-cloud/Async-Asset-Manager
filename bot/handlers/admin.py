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
        await query.answer("❌ Task non trovato.", show_alert=True)
        return

    session = await db.get_session_by_task(task_id)
    if not session:
        await query.answer("❌ Sessione non trovata.", show_alert=True)
        return

    if user_id not in (session["client_id"], session["executor_id"]):
        await query.answer("❌ Non autorizzato.", show_alert=True)
        return

    if session["status"] != "active":
        await query.answer("⚠️ La controversia è già stata aperta.", show_alert=True)
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
        # Increment disputes_initiated for the user who opened it
        await conn.execute(
            "UPDATE users SET disputes_initiated = disputes_initiated + 1 WHERE telegram_id = ?",
            (user_id,),
        )
        await conn.commit()

    # 3. Compile audit package
    messages = await db.get_deal_messages(task_id)
    msg_summary = ""
    for m in messages[-20:]:  # Last 20 messages
        role = "C" if m["sender_id"] == task["client_id"] else "E"
        msg_summary += f"[{role}] {m['message_type']}: {m['content_preview'][:80]}\n"

    audit_text = (
        f"🚨 <b>CONTROVERSIA APERTA</b>\n\n"
        f"🆔 Task #{task_id} — {task['title']}\n"
        f"👤 Committente: <code>{task['client_id']}</code>\n"
        f"🛠 Esecutore: <code>{task['executor_id']}</code>\n"
        f"💰 Importo escrow: <b>{task['reward_gross']:.2f} USDT</b>\n"
        f"📅 Categoria: {task.get('category', 'N/D')}\n"
        f"📋 Descrizione: {task.get('description', '')[:200]}\n\n"
        f"<b>Ultimi messaggi:</b>\n<pre>{msg_summary[:1000]}</pre>"
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
        logger.error("Impossibile inviare audit all'admin: %s", e)

    # Notify both parties
    for party_id in (task["client_id"], task["executor_id"]):
        try:
            await bot.send_message(
                chat_id=party_id,
                text=(
                    f"🚨 <b>Controversia aperta per Task #{task_id}</b>\n\n"
                    "Il nostro team esaminerà il caso e comunicherà la decisione.\n"
                    "La chat è stata sospesa."
                ),
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
        except Exception as e:
            logger.warning("Impossibile notificare parte %s: %s", party_id, e)


async def admin_release_executor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: release 90% to executor, 10% to platform."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TG_ID:
        await query.answer("🚫 Non autorizzato.", show_alert=True)
        return

    task_id = int(query.data.split("_", 2)[2])
    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text("❌ Task non trovato.")
        return

    ok = await db.release_to_executor(task_id)
    if not ok:
        await query.message.reply_text("❌ Errore nel rilascio dei fondi.")
        return

    # Increment client disputes_lost
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
        (task["client_id"], f"⚖️ Controversia Task #{task_id}: i fondi sono stati assegnati all'esecutore."),
        (task["executor_id"], f"🟢 Controversia Task #{task_id}: hai ricevuto il compenso di {task['reward_net']:.2f} USDT."),
    ]:
        try:
            await bot.send_message(chat_id=party_id, text=msg, reply_markup=MAIN_MENU)
        except Exception:
            pass

    await query.message.edit_text(
        query.message.text + f"\n\n✅ <b>Risolto: fondi rilasciati all'esecutore.</b>",
        parse_mode="HTML",
    )


async def admin_refund_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: full refund to client."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TG_ID:
        await query.answer("🚫 Non autorizzato.", show_alert=True)
        return

    task_id = int(query.data.split("_", 2)[2])
    task = await db.get_task(task_id)
    if not task:
        await query.message.reply_text("❌ Task non trovato.")
        return

    ok = await db.refund_client(task_id)
    if not ok:
        await query.message.reply_text("❌ Errore nel rimborso.")
        return

    # Increment executor disputes_lost
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
        (task["client_id"], f"🔴 Controversia Task #{task_id}: rimborso completato. {task['reward_gross']:.2f} USDT restituiti al tuo saldo."),
        (task["executor_id"], f"⚖️ Controversia Task #{task_id}: i fondi sono stati restituiti al committente."),
    ]:
        try:
            await bot.send_message(chat_id=party_id, text=msg, reply_markup=MAIN_MENU)
        except Exception:
            pass

    await query.message.edit_text(
        query.message.text + f"\n\n🔴 <b>Risolto: rimborso al committente.</b>",
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
        f"📊 <b>Statistiche Admin</b>\n\n"
        f"👥 Utenti registrati: {users_count}\n"
        f"📋 Task per stato:\n{task_lines}\n"
        f"💰 Commissioni totali: <b>{fees:.4f} USDT</b>",
        parse_mode="HTML",
    )
