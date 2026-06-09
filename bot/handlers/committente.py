import json
import logging
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import TELEGRAM_CHANNEL_ID, PLATFORM_FEE_RATE
from keyboards import (
    MAIN_MENU, CANCEL_KB, CATEGORY_KB, task_channel_kb, skip_attachments_kb
)
from states import TASK_TITLE, TASK_CATEGORY, TASK_DEADLINE, TASK_ATTACHMENTS, TASK_REWARD
from utils import validate_reward, calc_net_reward, is_blocked_file
import database as db

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Area Committente entry
# ──────────────────────────────────────────────

async def area_committente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0
    frozen = user["frozen_usdt"] if user else 0.0
    tasks = await db.get_user_tasks_as_client(user_id)
    open_tasks = [t for t in tasks if t["status"] == "open"]
    active_tasks = [t for t in tasks if t["status"] == "in_progress"]
    text = (
        "💼 <b>Area Committente</b>\n\n"
        f"💰 Saldo disponibile: <b>{bal:.2f} USDT</b>\n"
        f"🔒 In escrow: <b>{frozen:.2f} USDT</b>\n\n"
        f"📋 Incarichi aperti: {len(open_tasks)}\n"
        f"⚙️ Incarichi in corso: {len(active_tasks)}\n\n"
        "Usa <b>Pubblica Incarico</b> per creare un nuovo lavoro."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Pubblica Incarico", callback_data="start_task_wizard")],
        [InlineKeyboardButton("📋 I Miei Incarichi", callback_data="my_tasks_client")],
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ──────────────────────────────────────────────
# 4-Step task creation wizard
# ──────────────────────────────────────────────

async def start_task_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        send = query.message.reply_text
    else:
        send = update.message.reply_text

    context.user_data.clear()
    context.user_data["attachments"] = []

    await send(
        "📝 <b>Passo 1/4 — Titolo dell'incarico</b>\n\n"
        "Scrivi un titolo chiaro e conciso per il tuo incarico:",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return TASK_TITLE


async def task_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    title = update.message.text.strip()
    if len(title) < 5 or len(title) > 200:
        await update.message.reply_text(
            "⚠️ Il titolo deve essere tra 5 e 200 caratteri. Riprova:",
            reply_markup=CANCEL_KB,
        )
        return TASK_TITLE

    context.user_data["title"] = title
    await update.message.reply_text(
        "🏷 <b>Passo 2/4 — Categoria & Scadenza</b>\n\n"
        "Scegli la categoria:",
        parse_mode="HTML",
        reply_markup=CATEGORY_KB,
    )
    return TASK_CATEGORY


async def task_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "📅 Ora inserisci la <b>scadenza</b> dell'incarico (es. <i>15 luglio 2025</i> o <i>entro 3 giorni</i>):",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return TASK_DEADLINE


async def task_deadline_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    context.user_data["deadline"] = update.message.text.strip()
    await update.message.reply_text(
        "📎 <b>Passo 3/4 — Allegati</b>\n\n"
        "Invia file, immagini o documenti (fino a 50 MB ciascuno).\n"
        "Quando hai finito premi <b>⏭ Salta allegati</b> oppure invia i file.",
        parse_mode="HTML",
        reply_markup=skip_attachments_kb(),
    )
    return TASK_ATTACHMENTS


async def task_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    if update.message.text == "⏭ Salta allegati":
        return await proceed_to_reward(update, context)

    # Handle file/document/photo
    file_id = None
    file_name = ""

    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        if is_blocked_file(file_name):
            await update.message.reply_text(
                f"🚫 File <code>{file_name}</code> non consentito per sicurezza.",
                parse_mode="HTML",
            )
            return TASK_ATTACHMENTS
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
            return TASK_ATTACHMENTS
        atts.append(file_id)
        await update.message.reply_text(
            f"✅ Allegato {len(atts)}/10 ricevuto. Invia altri o premi ⏭.",
            reply_markup=skip_attachments_kb(),
        )
    else:
        await update.message.reply_text(
            "⚠️ Tipo di file non riconosciuto. Invia un documento, foto, video o audio.",
        )
    return TASK_ATTACHMENTS


async def proceed_to_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "💰 <b>Passo 4/4 — Compenso Lordo</b>\n\n"
        "Inserisci il compenso in <b>USDT</b> che vuoi offrire.\n"
        "⚠️ Verrà trattenuto il 10% come commissione piattaforma.\n"
        "Il 90% andrà all'esecutore al completamento.",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return TASK_REWARD


async def task_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    gross = validate_reward(update.message.text)
    if gross is None:
        await update.message.reply_text(
            "⚠️ Importo non valido. Inserisci un numero positivo (es. <code>15.00</code>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KB,
        )
        return TASK_REWARD

    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if not user or user["balance_usdt"] < gross:
        await update.message.reply_text(
            f"❌ Saldo insufficiente. Hai <b>{user['balance_usdt']:.2f} USDT</b>, "
            f"ma l'incarico richiede <b>{gross:.2f} USDT</b>.\n"
            "Ricarica il portafoglio con /portafoglio.",
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
    description = ud.get("description", title)

    # Freeze funds atomically
    ok = await db.freeze_funds(user_id, gross)
    if not ok:
        await update.message.reply_text(
            "❌ Errore nel bloccare i fondi. Riprova.",
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    # Insert task
    async with aiosqlite_connect() as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks (client_id, title, description, deadline, category, attachments, reward_gross, reward_net, status) "
            "VALUES (?,?,?,?,?,?,?,?,'open')",
            (user_id, title, description, deadline, category, attachments, gross, net),
        )
        task_id = cursor.lastrowid
        await conn.execute(
            "UPDATE users SET total_tasks_client = total_tasks_client + 1 WHERE telegram_id = ?",
            (user_id,),
        )
        await conn.commit()

    # Post to channel
    channel_text = (
        f"📋 <b>{title}</b> #PostProtetto\n\n"
        f"🏷 {category} | 📅 {deadline}\n"
        f"💰 Compenso: <b>{gross:.2f} USDT</b> (netto: {net:.2f})\n\n"
        f"🆔 Task #{task_id}"
    )
    try:
        msg = await update.get_bot().send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=channel_text,
            parse_mode="HTML",
            reply_markup=task_channel_kb(task_id),
        )
        async with aiosqlite_connect() as conn:
            await conn.execute(
                "UPDATE tasks SET channel_message_id = ? WHERE task_id = ?",
                (msg.message_id, task_id),
            )
            await conn.commit()
    except Exception as e:
        logger.error("Errore pubblicazione canale: %s", e)

    await update.message.reply_text(
        f"✅ <b>Incarico pubblicato!</b>\n\n"
        f"🆔 Task #{task_id} — {title}\n"
        f"💰 Fondi bloccati in escrow: <b>{gross:.2f} USDT</b>",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operazione annullata.", reply_markup=MAIN_MENU
    )
    return ConversationHandler.END


async def my_tasks_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = await db.get_user_tasks_as_client(user_id)
    if not tasks:
        await query.message.reply_text("📋 Nessun incarico pubblicato.")
        return
    for t in tasks[:10]:
        from utils import format_task_summary
        await query.message.reply_text(format_task_summary(t), parse_mode="HTML")


# Lazy import helper to avoid circular import
def aiosqlite_connect():
    import aiosqlite
    from database import DB_PATH
    return aiosqlite.connect(DB_PATH)
