import json
import logging
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import ContextTypes, ConversationHandler
from config import TELEGRAM_CHANNEL_ID, PLATFORM_FEE_RATE, STAR_TO_USDT_RATE
from keyboards import (
    MAIN_MENU, CANCEL_KB, CATEGORY_KB, task_channel_kb,
    skip_attachments_kb, task_payment_kb,
)
from states import TASK_TITLE, TASK_CATEGORY, TASK_DEADLINE, TASK_ATTACHMENTS, TASK_REWARD
from utils import validate_reward, calc_net_reward, calc_stars_for_usdt, is_blocked_file
import database as db

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Area Committente dashboard
# ──────────────────────────────────────────────

async def area_committente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0
    frozen = user["frozen_usdt"] if user else 0.0
    tasks = await db.get_user_tasks_as_client(user_id)
    open_tasks = [t for t in tasks if t["status"] == "open"]
    active_tasks = [t for t in tasks if t["status"] == "in_progress"]
    rating = user["client_rating"] if user else 5.0
    reviews = user["client_reviews_count"] if user else 0
    text = (
        "💼 <b>Area Committente</b>\n\n"
        f"💰 Saldo disponibile: <b>{bal:.2f} USDT</b>\n"
        f"🔒 In escrow: <b>{frozen:.2f} USDT</b>\n"
        f"⭐ Rating: <b>{rating:.1f}/5.0</b> ({reviews} recensioni)\n\n"
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
        "🏷 <b>Passo 2/4 — Categoria & Scadenza</b>\n\nScegli la categoria:",
        parse_mode="HTML",
        reply_markup=CATEGORY_KB,
    )
    return TASK_CATEGORY


async def task_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "📅 Inserisci la <b>scadenza</b> dell'incarico\n(es. <i>15 luglio 2025</i> o <i>entro 3 giorni</i>):",
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
        "Quando hai finito premi <b>⏭ Salta allegati</b>.",
        parse_mode="HTML",
        reply_markup=skip_attachments_kb(),
    )
    return TASK_ATTACHMENTS


async def task_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Annulla":
        return await cancel_wizard(update, context)

    if update.message.text == "⏭ Salta allegati":
        return await proceed_to_reward(update, context)

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
        "⚠️ Il 90% andrà all'esecutore al completamento (10% commissione piattaforma).\n\n"
        "Puoi pagare l'escrow con il tuo saldo USDT <b>oppure</b> con <b>Telegram Stars</b>.",
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

    net = calc_net_reward(gross, PLATFORM_FEE_RATE)
    stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
    ud = context.user_data

    # Store all task data in user_data for the payment step
    context.user_data["pending_task"] = {
        "title": ud.get("title", ""),
        "category": ud.get("category", "🌐 Generale"),
        "deadline": ud.get("deadline", "N/D"),
        "attachments": json.dumps(ud.get("attachments", [])),
        "gross": gross,
        "net": net,
    }

    user = await db.get_user(update.effective_user.id)
    bal = user["balance_usdt"] if user else 0.0

    await update.message.reply_text(
        f"💳 <b>Metodo di pagamento escrow</b>\n\n"
        f"Compenso lordo: <b>{gross:.2f} USDT</b>\n"
        f"Netto esecutore: <b>{net:.2f} USDT</b>\n\n"
        f"💵 Il tuo saldo USDT: <b>{bal:.2f}</b>\n"
        f"⭐ Equivalente Stars: <b>{stars_needed} Stars</b>\n\n"
        "Scegli come vuoi pagare:",
        parse_mode="HTML",
        reply_markup=task_payment_kb(),
    )
    return ConversationHandler.END


# ──────────────────────────────────────────────
# Payment method callbacks (outside ConversationHandler)
# ──────────────────────────────────────────────

async def task_pay_usdt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pay for task escrow from internal USDT balance."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    pending = context.user_data.get("pending_task")
    if not pending:
        await query.message.reply_text(
            "❌ Sessione scaduta. Ricrea l'incarico.", reply_markup=MAIN_MENU
        )
        return

    gross = pending["gross"]
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0

    if not user or bal < gross:
        stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
        await query.message.reply_text(
            f"❌ Saldo insufficiente. Hai <b>{bal:.2f} USDT</b>, "
            f"ma l'incarico richiede <b>{gross:.2f} USDT</b>.\n\n"
            f"Puoi ricaricare con 💰 Portafoglio oppure pagare con "
            f"<b>{stars_needed} Telegram Stars</b>:",
            parse_mode="HTML",
            reply_markup=task_payment_kb(),
        )
        return

    ok = await db.freeze_funds(user_id, gross)
    if not ok:
        await query.message.reply_text("❌ Errore nel bloccare i fondi. Riprova.", reply_markup=MAIN_MENU)
        return

    task_id = await _insert_task(user_id, pending)
    context.user_data.pop("pending_task", None)
    await _post_to_channel(update.get_bot(), task_id, pending)

    await query.message.reply_text(
        f"✅ <b>Incarico pubblicato!</b>\n\n"
        f"🆔 Task #{task_id} — {pending['title']}\n"
        f"💰 Fondi bloccati in escrow: <b>{gross:.2f} USDT</b>",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )


async def task_pay_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pay for task escrow with Telegram Stars."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    pending = context.user_data.get("pending_task")
    if not pending:
        await query.message.reply_text(
            "❌ Sessione scaduta. Ricrea l'incarico.", reply_markup=MAIN_MENU
        )
        return

    gross = pending["gross"]
    stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
    title_short = pending["title"][:50]

    await context.bot.send_invoice(
        chat_id=user_id,
        title=f"Escrow: {title_short}",
        description=(
            f"Pubblica incarico su Fai un Salto\n"
            f"Importo escrow: {gross:.2f} USDT"
        ),
        payload=f"task_stars_{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Stars per escrow", amount=stars_needed)],
        provider_token="",
    )


# ──────────────────────────────────────────────
# Shared task creation helpers
# ──────────────────────────────────────────────

async def _insert_task(client_id: int, pending: dict) -> int:
    """Insert a task row and return the new task_id."""
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks "
            "(client_id, title, description, deadline, category, attachments, reward_gross, reward_net, status) "
            "VALUES (?,?,?,?,?,?,?,?,'open')",
            (
                client_id,
                pending["title"],
                pending["title"],
                pending["deadline"],
                pending["category"],
                pending["attachments"],
                pending["gross"],
                pending["net"],
            ),
        )
        task_id = cursor.lastrowid
        await conn.commit()
    return task_id


async def _post_to_channel(bot, task_id: int, pending: dict) -> None:
    """Post a task card to the public channel."""
    import aiosqlite
    from database import DB_PATH
    gross = pending["gross"]
    net = pending["net"]
    title = pending["title"]
    category = pending.get("category", "🌐 Generale")
    deadline = pending.get("deadline", "N/D")

    channel_text = (
        f"📋 <b>{title}</b> #PostProtetto\n\n"
        f"🏷 {category} | 📅 {deadline}\n"
        f"💰 Compenso: <b>{gross:.2f} USDT</b> (netto: {net:.2f})\n\n"
        f"🆔 Task #{task_id}"
    )
    try:
        msg = await bot.send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=channel_text,
            parse_mode="HTML",
            reply_markup=task_channel_kb(task_id),
        )
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "UPDATE tasks SET channel_message_id = ? WHERE task_id = ?",
                (msg.message_id, task_id),
            )
            await conn.commit()
    except Exception as e:
        logger.error("Errore pubblicazione canale: %s", e)


# ──────────────────────────────────────────────
# Cancel wizard
# ──────────────────────────────────────────────

async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


# ──────────────────────────────────────────────
# My tasks (inline callback)
# ──────────────────────────────────────────────

async def my_tasks_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = await db.get_user_tasks_as_client(user_id)
    if not tasks:
        await query.message.reply_text("📋 Nessun incarico pubblicato.")
        return
    from utils import format_task_summary
    for t in tasks[:10]:
        await query.message.reply_text(format_task_summary(t), parse_mode="HTML")
