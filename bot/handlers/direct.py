"""
Direct Deal flow — private invite-only task between a specific client and executor.

Flow:
  1. Client presses "🤝 Nuovo Affare Diretto"
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
# Entry point
# ─────────────────────────────────────────────

async def direct_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["attachments"] = []
    await update.message.reply_text(
        "🤝 <b>Nuovo Affare Diretto</b>\n\n"
        "Inserisci lo <b>username Telegram</b> dell'esecutore con cui vuoi collaborare.\n"
        "Es: <code>@mario_rossi</code>",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_TARGET


# ─────────────────────────────────────────────
# Step 1 — Target executor username
# ─────────────────────────────────────────────

async def direct_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await direct_cancel(update, context)

    raw = update.message.text.strip()
    username = raw if raw.startswith("@") else f"@{raw}"

    if len(username) < 2 or not username[1:].replace("_", "").isalnum():
        await update.message.reply_text(
            "⚠️ Username non valido. Inserisci un username Telegram valido (es. <code>@mario_rossi</code>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KB,
        )
        return DIRECT_TARGET

    context.user_data["direct_target"] = username
    await update.message.reply_text(
        f"👤 Esecutore selezionato: <b>{username}</b>\n\n"
        "📝 <b>Passo 1/5 — Titolo dell'incarico</b>\n\n"
        "Scrivi un titolo chiaro e conciso:",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_TITLE


# ─────────────────────────────────────────────
# Step 2 — Title
# ─────────────────────────────────────────────

async def direct_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await direct_cancel(update, context)

    title = update.message.text.strip()
    if len(title) < 5 or len(title) > 200:
        await update.message.reply_text(
            "⚠️ Il titolo deve essere tra 5 e 200 caratteri. Riprova:",
            reply_markup=CANCEL_KB,
        )
        return DIRECT_TITLE

    context.user_data["title"] = title
    await update.message.reply_text(
        "🏷 <b>Passo 2/5 — Categoria</b>\n\nScegli la categoria dell'incarico:",
        parse_mode="HTML",
        reply_markup=CATEGORY_KB,
    )
    return DIRECT_CATEGORY


# ─────────────────────────────────────────────
# Step 3 — Category + Deadline
# ─────────────────────────────────────────────

async def direct_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await direct_cancel(update, context)

    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "📅 <b>Passo 3/5 — Scadenza</b>\n\n"
        "Inserisci la scadenza (es. <i>20 luglio 2025</i> o <i>entro 5 giorni</i>):",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_DEADLINE


async def direct_deadline_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await direct_cancel(update, context)

    context.user_data["deadline"] = update.message.text.strip()
    await update.message.reply_text(
        "📎 <b>Passo 4/5 — Allegati</b>\n\n"
        "Invia file, immagini o documenti (fino a 50 MB ciascuno).\n"
        "Quando hai finito premi <b>⏭ Salta allegati</b>.",
        parse_mode="HTML",
        reply_markup=skip_attachments_kb(),
    )
    return DIRECT_ATTACHMENTS


# ─────────────────────────────────────────────
# Step 4 — Attachments
# ─────────────────────────────────────────────

async def direct_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await direct_cancel(update, context)

    if update.message.text == "⏭ Salta allegati":
        return await _proceed_to_direct_reward(update, context)

    file_id = None
    file_name = ""

    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        if is_blocked_file(file_name):
            await update.message.reply_text(
                f"🚫 File <code>{file_name}</code> non consentito.",
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
            await update.message.reply_text("⚠️ Massimo 10 allegati. Premi ⏭ per continuare.")
            return DIRECT_ATTACHMENTS
        atts.append(file_id)
        await update.message.reply_text(
            f"✅ Allegato {len(atts)}/10 ricevuto. Invia altri o premi ⏭.",
            reply_markup=skip_attachments_kb(),
        )
    else:
        await update.message.reply_text("⚠️ Tipo di file non riconosciuto.")
    return DIRECT_ATTACHMENTS


async def _proceed_to_direct_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "💰 <b>Passo 5/5 — Compenso Lordo</b>\n\n"
        "Inserisci il compenso in <b>USDT</b> che vuoi offrire.\n"
        "⚠️ Il 10% viene trattenuto come commissione piattaforma.\n"
        "Il 90% andrà all'esecutore al completamento.",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return DIRECT_REWARD


# ─────────────────────────────────────────────
# Step 5 — Reward → create task & send deep link
# ─────────────────────────────────────────────

async def direct_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await direct_cancel(update, context)

    gross = validate_reward(update.message.text)
    if gross is None:
        await update.message.reply_text(
            "⚠️ Importo non valido. Inserisci un numero positivo (es. <code>20.00</code>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KB,
        )
        return DIRECT_REWARD

    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user or user["balance_usdt"] < gross:
        bal = user["balance_usdt"] if user else 0.0
        await update.message.reply_text(
            f"❌ Saldo insufficiente. Hai <b>{bal:.2f} USDT</b>, "
            f"ma l'incarico richiede <b>{gross:.2f} USDT</b>.\n"
            "Ricarica il portafoglio con 💰 Portafoglio.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    net = calc_net_reward(gross, PLATFORM_FEE_RATE)
    ud = context.user_data
    title = ud["title"]
    category = ud.get("category", "🌐 Generale")
    deadline = ud.get("deadline", "N/D")
    attachments = json.dumps(ud.get("attachments", []))
    target_username = ud["direct_target"]

    # Generate unique invite token (12 hex chars)
    token = uuid.uuid4().hex[:TOKEN_LEN]
    identity = f"{target_username}|{token}"

    # Atomically freeze funds
    ok = await freeze_funds(user_id, gross)
    if not ok:
        await update.message.reply_text("❌ Errore nel bloccare i fondi. Riprova.", reply_markup=MAIN_MENU)
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
        [InlineKeyboardButton("🔗 Apri link invito", url=deep_link)]
    ])

    await update.message.reply_text(
        f"✅ <b>Affare diretto creato!</b>\n\n"
        f"🆔 Task #{task_id} — {title}\n"
        f"👤 Per: <b>{target_username}</b>\n"
        f"💰 Escrow bloccato: <b>{gross:.2f} USDT</b>\n\n"
        f"📩 Invia questo link a {target_username} per far accettare l'incarico:\n"
        f"<code>{deep_link}</code>",
        parse_mode="HTML",
        reply_markup=share_kb,
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─────────────────────────────────────────────
# Deep-link entry: /start direct_<TOKEN>
# ─────────────────────────────────────────────

async def handle_direct_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called when executor opens the bot via a direct deal invite link."""
    token = context.args[0][len("direct_"):]  # strip "direct_" prefix
    user_id = update.effective_user.id

    # Look up the task by token
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE is_direct=1 AND status='open' AND target_executor_identity LIKE ?",
            (f"%|{token}",),
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await update.message.reply_text(
            "❌ Link non valido o incarico non più disponibile.",
            reply_markup=MAIN_MENU,
        )
        return

    task = dict(task)

    if task["client_id"] == user_id:
        await update.message.reply_text(
            "⚠️ Non puoi accettare il tuo stesso incarico.",
            reply_markup=MAIN_MENU,
        )
        return

    # Parse username from identity
    target_username = task["target_executor_identity"].split("|")[0]

    await update.message.reply_text(
        f"🤝 <b>Proposta di Affare Diretto</b>\n\n"
        f"📋 <b>{task['title']}</b>\n"
        f"🏷 {task.get('category', 'Generale')} | 📅 {task.get('deadline', 'N/D')}\n"
        f"💰 Compenso netto per te: <b>{task['reward_net']:.2f} USDT</b>\n\n"
        f"Accetti questo incarico?",
        parse_mode="HTML",
        reply_markup=direct_deal_offer_kb(task["task_id"], token),
    )


# ─────────────────────────────────────────────
# Accept / Decline callbacks
# ─────────────────────────────────────────────

async def direct_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    parts = query.data.split("_")
    # pattern: direct_accept_{task_id}_{token}
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
        await query.answer("❌ Incarico non più disponibile.", show_alert=True)
        return

    task = dict(task)

    if task["client_id"] == user_id:
        await query.answer("⚠️ Non puoi accettare il tuo stesso incarico.", show_alert=True)
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
            await query.answer("❌ Incarico già assegnato.", show_alert=True)
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
                f"🎉 <b>Affare Diretto accettato!</b>\n\n"
                f"Task #{task_id} — {task['title']}\n"
                f"L'esecutore ha accettato la tua proposta. La chat è ora attiva.\n"
                "Scrivi qui per comunicare in modo anonimo."
            ),
            parse_mode="HTML",
            reply_markup=client_room_kb(task_id),
        )
    except Exception as e:
        logger.error("Impossibile notificare committente diretto: %s", e)

    await query.message.reply_text(
        f"✅ <b>Incarico accettato!</b>\n\n"
        f"Task #{task_id} — {task['title']}\n"
        f"💰 Compenso netto: <b>{task['reward_net']:.2f} USDT</b>\n\n"
        "Scrivi qui per comunicare con il committente in modo anonimo.",
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
        await query.answer("❌ Incarico già gestito.", show_alert=True)
        return

    task = dict(task)

    # Full refund to client
    await refund_client(task_id)

    # Notify client
    try:
        await context.bot.send_message(
            chat_id=task["client_id"],
            text=(
                f"❌ <b>Affare Diretto rifiutato</b>\n\n"
                f"Task #{task_id} — {task['title']}\n"
                f"L'esecutore ha rifiutato la proposta.\n"
                f"💰 <b>{task['reward_gross']:.2f} USDT</b> restituiti al tuo saldo."
            ),
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
    except Exception as e:
        logger.error("Impossibile notificare committente del rifiuto: %s", e)

    await query.message.reply_text(
        f"Hai rifiutato l'incarico <b>{task['title']}</b>.\n"
        "Puoi esplorare altri incarichi dal canale.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )


# ─────────────────────────────────────────────
# Cancel
# ─────────────────────────────────────────────

async def direct_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=MAIN_MENU)
    return ConversationHandler.END
