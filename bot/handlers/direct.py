"""
Direct Deal flow — private invite-only task between a specific client and executor.

Flow:
  1. Client presses "🤝 Neues Direktgeschäft"
  2. Wizard collects: target @username, title, category, deadline, attachments, reward
  3. Funds are frozen; task is created as is_direct=1
  4. Client receives a unique deep-link to forward to the executor
  5. Executor opens the link (/start direct_<TOKEN>) → sees the offer
  6. Executor accepts → deal session opens, chat bridge activates
  7. Executor declines → full refund to client, task cancelled
"""

import json
import logging
import uuid

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import PLATFORM_FEE_RATE
from database import DB_PATH, freeze_funds, get_user, refund_client, create_deal_session
from keyboards import (
    CANCEL_KB,
    CATEGORY_KB,
    MAIN_MENU,
    client_room_kb,
    direct_deal_offer_kb,
    executor_room_kb,
    skip_attachments_kb,
)
from states import (
    DIRECT_ATTACHMENTS,
    DIRECT_CATEGORY,
    DIRECT_DEADLINE,
    DIRECT_REWARD,
    DIRECT_TARGET,
    DIRECT_TITLE,
)
from utils import calc_net_reward, is_blocked_file, validate_reward

logger = logging.getLogger(__name__)

TOKEN_LEN = 12  # hex chars — short enough for callback_data safety


# ─────────────────────────────────────────────
# Einstiegspunkt
# ─────────────────────────────────────────────

async def direct_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["attachments"] = []
    await update.message.reply_text(
        "🤝 <b>Neues Direktgeschäft</b>\n\n"
        "Gib den <b>Telegram-Benutzernamen</b> des Auftragnehmers ein, mit dem du zusammenarbeiten möchtest.\n"
        "Bsp: <code>@max_mustermann</code>",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_TARGET


# ─────────────────────────────────────────────
# Schritt 1 — Ziel-Auftragnehmer-Username
# ─────────────────────────────────────────────

async def direct_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await direct_cancel(update, context)

    raw = update.message.text.strip()
    username = raw if raw.startswith("@") else f"@{raw}"

    if len(username) < 2 or not username[1:].replace("_", "").isalnum():
        await update.message.reply_text(
            "⚠️ Ungültiger Benutzername. Gib einen gültigen Telegram-Benutzernamen ein (z.B. <code>@max_mustermann</code>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KB,
        )
        return DIRECT_TARGET

    context.user_data["direct_target"] = username
    await update.message.reply_text(
        f"👤 Ausgewählter Auftragnehmer: <b>{username}</b>\n\n"
        "📝 <b>Schritt 1/5 — Aufragstitel</b>\n\n"
        "Schreibe einen klaren und prägnanten Titel:",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_TITLE


# ─────────────────────────────────────────────
# Schritt 2 — Titel
# ─────────────────────────────────────────────

async def direct_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await direct_cancel(update, context)

    title = update.message.text.strip()
    if len(title) < 5 or len(title) > 200:
        await update.message.reply_text(
            "⚠️ Der Titel muss zwischen 5 und 200 Zeichen lang sein. Nochmal versuchen:",
            reply_markup=CANCEL_KB,
        )
        return DIRECT_TITLE

    context.user_data["title"] = title
    await update.message.reply_text(
        "🏷 <b>Schritt 2/5 — Kategorie</b>\n\nWähle die Kategorie des Auftrags:",
        parse_mode="HTML",
        reply_markup=CATEGORY_KB,
    )
    return DIRECT_CATEGORY


# ─────────────────────────────────────────────
# Schritt 3 — Kategorie + Frist
# ─────────────────────────────────────────────

async def direct_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await direct_cancel(update, context)

    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "📅 <b>Schritt 3/5 — Frist</b>\n\n"
        "Gib die Frist ein (z.B. <i>20. Juli 2025</i> oder <i>innerhalb von 5 Tagen</i>):",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_DEADLINE


async def direct_deadline_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await direct_cancel(update, context)

    context.user_data["deadline"] = update.message.text.strip()
    await update.message.reply_text(
        "📎 <b>Schritt 4/5 — Anhänge</b>\n\n"
        "Sende Dateien, Bilder oder Dokumente (bis zu 50 MB pro Datei).\n"
        "Wenn du fertig bist, drücke <b>⏭ Anhänge überspringen</b>.",
        parse_mode="HTML",
        reply_markup=skip_attachments_kb(),
    )
    return DIRECT_ATTACHMENTS


# ─────────────────────────────────────────────
# Schritt 4 — Anhänge
# ─────────────────────────────────────────────

async def direct_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await direct_cancel(update, context)

    if update.message.text == "⏭ Anhänge überspringen":
        return await _proceed_to_direct_reward(update, context)

    file_id = None
    file_name = ""

    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        if is_blocked_file(file_name):
            await update.message.reply_text(
                f"🚫 Datei <code>{file_name}</code> nicht erlaubt.",
                parse_mode="HTML",
            )
            return DIRECT_ATTACHMENTS
        file_id = doc.file_id
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.video:
        file_id = update.message.video.file_id
    elif update.message.audio:
        file_id = update.message.audio.file_id

    if file_id:
        atts = context.user_data.setdefault("attachments", [])
        if len(atts) >= 10:
            await update.message.reply_text("⚠️ Maximal 10 Anhänge. Drücke ⏭ zum Fortfahren.")
            return DIRECT_ATTACHMENTS
        atts.append(file_id)
        await update.message.reply_text(
            f"✅ Anhang {len(atts)}/10 empfangen. Weitere senden oder ⏭ drücken.",
            reply_markup=skip_attachments_kb(),
        )
    else:
        await update.message.reply_text("⚠️ Unbekannter Dateityp.")
    return DIRECT_ATTACHMENTS


async def _proceed_to_direct_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "💰 <b>Schritt 5/5 — Bruttovergütung</b>\n\n"
        "Gib die Vergütung in <b>USDT</b> ein, die du anbieten möchtest.\n"
        "⚠️ 10% werden als Plattformgebühr einbehalten.\n"
        "90% gehen bei Abschluss an den Auftragnehmer.",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_REWARD


# ─────────────────────────────────────────────
# Schritt 5 — Vergütung → Auftrag erstellen & Deep-Link senden
# ─────────────────────────────────────────────

async def direct_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await direct_cancel(update, context)

    gross = validate_reward(update.message.text)
    if gross is None:
        await update.message.reply_text(
            "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>20.00</code>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KB,
        )
        return DIRECT_REWARD

    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user or user["balance_usdt"] < gross:
        bal = user["balance_usdt"] if user else 0.0
        await update.message.reply_text(
            f"❌ Unzureichendes Guthaben. Du hast <b>{bal:.2f} USDT</b>, "
            f"der Auftrag erfordert jedoch <b>{gross:.2f} USDT</b>.\n"
            "Lade dein Wallet über 💰 Wallet auf.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    net = calc_net_reward(gross, PLATFORM_FEE_RATE)
    ud = context.user_data
    title = ud["title"]
    category = ud.get("category", "🌐 Allgemein")
    deadline = ud.get("deadline", "k.A.")
    attachments = json.dumps(ud.get("attachments", []))
    target_username = ud["direct_target"]

    # Generate unique invite token (12 hex chars)
    token = uuid.uuid4().hex[:TOKEN_LEN]
    identity = f"{target_username}|{token}"

    # Atomically freeze funds
    ok = await freeze_funds(user_id, gross)
    if not ok:
        await update.message.reply_text("❌ Fehler beim Einfrieren der Mittel. Bitte erneut versuchen.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    # Insert task as direct
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks "
            "(client_id, title, description, deadline, category, attachments, "
            " reward_gross, reward_net, status, is_direct, target_executor_identity) "
            "VALUES (?,?,?,?,?,?,?,?,'open',1,?)",
            (user_id, title, title, deadline, category, attachments, gross, net, identity),
        )
        task_id = cursor.lastrowid
        await conn.execute(
            "UPDATE users SET total_tasks_client = total_tasks_client + 1 WHERE telegram_id = ?",
            (user_id,),
        )
        await conn.commit()

    # Build deep link
    bot_user = await update.get_bot().get_me()
    deep_link = f"https://t.me/{bot_user.username}?start=direct_{token}"

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    share_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Einladungslink öffnen", url=deep_link)]
    ])

    await update.message.reply_text(
        f"✅ <b>Direktgeschäft erstellt!</b>\n\n"
        f"🆔 Auftrag #{task_id} — {title}\n"
        f"👤 Für: <b>{target_username}</b>\n"
        f"💰 Treuhand eingefroren: <b>{gross:.2f} USDT</b>\n\n"
        f"📩 Schicke diesen Link an {target_username}, damit er/sie den Auftrag annehmen kann:\n"
        f"<code>{deep_link}</code>",
        parse_mode="HTML",
        reply_markup=share_kb,
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────
# Deep-Link-Einstieg: /start direct_<TOKEN>
# ─────────────────────────────────────────────

async def handle_direct_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called when executor opens the bot via a direct deal invite link."""
    token = context.args[0][len("direct_"):]  # strip "direct_" prefix
    user_id = update.effective_user.id

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE is_direct=1 AND status='open' AND target_executor_identity LIKE ?",
            (f"%|{token}",),
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await update.message.reply_text(
            "❌ Ungültiger Link oder Auftrag nicht mehr verfügbar.",
            reply_markup=MAIN_MENU,
        )
        return

    task = dict(task)

    if task["client_id"] == user_id:
        await update.message.reply_text(
            "⚠️ Du kannst deinen eigenen Auftrag nicht annehmen.",
            reply_markup=MAIN_MENU,
        )
        return

    target_username = task["target_executor_identity"].split("|")[0]

    await update.message.reply_text(
        f"🤝 <b>Direktgeschäft-Angebot</b>\n\n"
        f"📋 <b>{task['title']}</b>\n"
        f"🏷 {task.get('category', 'Allgemein')} | 📅 {task.get('deadline', 'k.A.')}\n"
        f"💰 Nettovergütung für dich: <b>{task['reward_net']:.2f} USDT</b>\n\n"
        f"Nimmst du diesen Auftrag an?",
        parse_mode="HTML",
        reply_markup=direct_deal_offer_kb(task["task_id"], token),
    )


# ─────────────────────────────────────────────
# Annehmen / Ablehnen Callbacks
# ─────────────────────────────────────────────

async def direct_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    parts = query.data.split("_")
    task_id = int(parts[2])
    token = parts[3]

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE task_id=? AND status='open' AND is_direct=1",
            (task_id,),
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await query.answer("❌ Auftrag nicht mehr verfügbar.", show_alert=True)
        return

    task = dict(task)

    if task["client_id"] == user_id:
        await query.answer("⚠️ Du kannst deinen eigenen Auftrag nicht annehmen.", show_alert=True)
        return

    # Atomically claim the task
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("BEGIN")
        async with conn.execute(
            "SELECT status FROM tasks WHERE task_id=?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] != "open":
            await conn.execute("ROLLBACK")
            await query.answer("❌ Auftrag bereits vergeben.", show_alert=True)
            return
        await conn.execute(
            "UPDATE tasks SET status='in_progress', executor_id=?, claimed_at=CURRENT_TIMESTAMP WHERE task_id=?",
            (user_id, task_id),
        )
        await conn.execute("COMMIT")

    # Open deal session
    room_token = uuid.uuid4().hex
    await create_deal_session(task_id, task["client_id"], user_id, room_token)

    bot = context.bot

    # Notify client
    try:
        await bot.send_message(
            chat_id=task["client_id"],
            text=(
                f"🎉 <b>Direktgeschäft angenommen!</b>\n\n"
                f"Auftrag #{task_id} — {task['title']}\n"
                f"Der Auftragnehmer hat dein Angebot angenommen. Der Chat ist jetzt aktiv.\n"
                "Schreibe hier, um anonym zu kommunizieren."
            ),
            parse_mode="HTML",
            reply_markup=client_room_kb(task_id),
        )
    except Exception as e:
        logger.error("Auftraggeber des Direktgeschäfts konnte nicht benachrichtigt werden: %s", e)

    await query.message.reply_text(
        f"✅ <b>Auftrag angenommen!</b>\n\n"
        f"Auftrag #{task_id} — {task['title']}\n"
        f"💰 Nettovergütung: <b>{task['reward_net']:.2f} USDT</b>\n\n"
        "Schreibe hier, um anonym mit dem Auftraggeber zu kommunizieren.",
        parse_mode="HTML",
        reply_markup=executor_room_kb(task_id),
    )


async def direct_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    task_id = int(parts[2])

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE task_id=? AND status='open' AND is_direct=1",
            (task_id,),
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await query.answer("❌ Auftrag bereits bearbeitet.", show_alert=True)
        return

    task = dict(task)

    # Full refund to client
    await refund_client(task_id)

    # Notify client
    try:
        await context.bot.send_message(
            chat_id=task["client_id"],
            text=(
                f"❌ <b>Direktgeschäft abgelehnt</b>\n\n"
                f"Auftrag #{task_id} — {task['title']}\n"
                f"Der Auftragnehmer hat das Angebot abgelehnt.\n"
                f"💰 <b>{task['reward_gross']:.2f} USDT</b> deinem Guthaben zurückgebucht."
            ),
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
    except Exception as e:
        logger.error("Auftraggeber über Ablehnung konnte nicht benachrichtigt werden: %s", e)

    await query.message.reply_text(
        f"Du hast den Auftrag <b>{task['title']}</b> abgelehnt.\n"
        "Du kannst weitere Aufträge im Kanal erkunden.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )


# ─────────────────────────────────────────────
# Abbrechen
# ─────────────────────────────────────────────

async def direct_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Vorgang abgebrochen.", reply_markup=MAIN_MENU)
    return ConversationHandler.END
