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
# Auftraggeber-Dashboard
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
        "💼 <b>Auftraggeber-Bereich</b>\n\n"
        f"💰 Verfügbares Guthaben: <b>{bal:.2f} USDT</b>\n"
        f"🔒 Im Treuhand: <b>{frozen:.2f} USDT</b>\n"
        f"⭐ Bewertung: <b>{rating:.1f}/5.0</b> ({reviews} Bewertungen)\n\n"
        f"📋 Offene Aufträge: {len(open_tasks)}\n"
        f"⚙️ Laufende Aufträge: {len(active_tasks)}\n\n"
        "Nutze <b>Auftrag veröffentlichen</b>, um einen neuen Job zu erstellen."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Auftrag veröffentlichen", callback_data="start_task_wizard")],
        [InlineKeyboardButton("📋 Meine Aufträge", callback_data="my_tasks_client")],
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ──────────────────────────────────────────────
# 4-Schritt Auftrags-Assistent
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
        "📝 <b>Schritt 1/4 — Aufragstitel</b>\n\n"
        "Schreibe einen klaren und prägnanten Titel für deinen Auftrag:",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return TASK_TITLE


async def task_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await cancel_wizard(update, context)

    title = update.message.text.strip()
    if len(title) < 5 or len(title) > 200:
        await update.message.reply_text(
            "⚠️ Der Titel muss zwischen 5 und 200 Zeichen lang sein. Nochmal versuchen:",
            reply_markup=CANCEL_KB,
        )
        return TASK_TITLE

    context.user_data["title"] = title
    await update.message.reply_text(
        "🏷 <b>Schritt 2/4 — Kategorie & Frist</b>\n\nWähle die Kategorie:",
        parse_mode="HTML",
        reply_markup=CATEGORY_KB,
    )
    return TASK_CATEGORY


async def task_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await cancel_wizard(update, context)

    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "📅 Gib die <b>Frist</b> des Auftrags ein\n(z.B. <i>15. Juli 2025</i> oder <i>innerhalb von 3 Tagen</i>):",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return TASK_DEADLINE


async def task_deadline_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await cancel_wizard(update, context)

    context.user_data["deadline"] = update.message.text.strip()
    await update.message.reply_text(
        "📎 <b>Schritt 3/4 — Anhänge</b>\n\n"
        "Sende Dateien, Bilder oder Dokumente (bis zu 50 MB pro Datei).\n"
        "Wenn du fertig bist, drücke <b>⏭ Anhänge überspringen</b>.",
        parse_mode="HTML",
        reply_markup=skip_attachments_kb(),
    )
    return TASK_ATTACHMENTS


async def task_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await cancel_wizard(update, context)

    if update.message.text == "⏭ Anhänge überspringen":
        return await proceed_to_reward(update, context)

    file_id = None
    file_name = ""

    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        if is_blocked_file(file_name):
            await update.message.reply_text(
                f"🚫 Datei <code>{file_name}</code> aus Sicherheitsgründen nicht erlaubt.",
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
            await update.message.reply_text("⚠️ Maximal 10 Anhänge. Drücke ⏭ zum Fortfahren.")
            return TASK_ATTACHMENTS
        atts.append(file_id)
        await update.message.reply_text(
            f"✅ Anhang {len(atts)}/10 empfangen. Weitere senden oder ⏭ drücken.",
            reply_markup=skip_attachments_kb(),
        )
    else:
        await update.message.reply_text(
            "⚠️ Unbekannter Dateityp. Sende ein Dokument, Foto, Video oder Audio.",
        )
    return TASK_ATTACHMENTS


async def proceed_to_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "💰 <b>Schritt 4/4 — Bruttovergütung</b>\n\n"
        "Gib die Vergütung in <b>USDT</b> ein, die du anbieten möchtest.\n"
        "⚠️ 90% gehen bei Abschluss an den Auftragnehmer (10% Plattformgebühr).\n\n"
        "Du kannst den Treuhandbetrag mit deinem USDT-Guthaben <b>oder</b> mit <b>Telegram Stars</b> bezahlen.",
        parse_mode="HTML",
        reply_markup=CANCEL_KB,
    )
    return TASK_REWARD


async def task_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Abbrechen":
        return await cancel_wizard(update, context)

    gross = validate_reward(update.message.text)
    if gross is None:
        await update.message.reply_text(
            "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>15.00</code>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KB,
        )
        return TASK_REWARD

    net = calc_net_reward(gross, PLATFORM_FEE_RATE)
    stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
    ud = context.user_data

    context.user_data["pending_task"] = {
        "title": ud.get("title", ""),
        "category": ud.get("category", "🌐 Allgemein"),
        "deadline": ud.get("deadline", "k.A."),
        "attachments": json.dumps(ud.get("attachments", [])),
        "gross": gross,
        "net": net,
    }

    user = await db.get_user(update.effective_user.id)
    bal = user["balance_usdt"] if user else 0.0

    await update.message.reply_text(
        f"💳 <b>Treuhand-Zahlungsmethode</b>\n\n"
        f"Bruttovergütung: <b>{gross:.2f} USDT</b>\n"
        f"Netto Auftragnehmer: <b>{net:.2f} USDT</b>\n\n"
        f"💵 Dein USDT-Guthaben: <b>{bal:.2f}</b>\n"
        f"⭐ Stars-Äquivalent: <b>{stars_needed} Stars</b>\n\n"
        "Wähle die Zahlungsmethode:",
        parse_mode="HTML",
        reply_markup=task_payment_kb(),
    )
    return ConversationHandler.END


# ──────────────────────────────────────────────
# Zahlungs-Callbacks (außerhalb ConversationHandler)
# ──────────────────────────────────────────────

async def task_pay_usdt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pay for task escrow from internal USDT balance."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    pending = context.user_data.get("pending_task")
    if not pending:
        await query.message.reply_text(
            "❌ Sitzung abgelaufen. Bitte Auftrag neu erstellen.", reply_markup=MAIN_MENU
        )
        return

    gross = pending["gross"]
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0

    if not user or bal < gross:
        stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
        await query.message.reply_text(
            f"❌ Unzureichendes Guthaben. Du hast <b>{bal:.2f} USDT</b>, "
            f"der Auftrag erfordert jedoch <b>{gross:.2f} USDT</b>.\n\n"
            f"Du kannst über 💰 Wallet aufladen oder mit "
            f"<b>{stars_needed} Telegram Stars</b> zahlen:",
            parse_mode="HTML",
            reply_markup=task_payment_kb(),
        )
        return

    ok = await db.freeze_funds(user_id, gross)
    if not ok:
        await query.message.reply_text("❌ Fehler beim Einfrieren der Mittel. Bitte erneut versuchen.", reply_markup=MAIN_MENU)
        return

    task_id = await _insert_task(user_id, pending)
    context.user_data.pop("pending_task", None)
    await _post_to_channel(update.get_bot(), task_id, pending)

    await query.message.reply_text(
        f"✅ <b>Auftrag veröffentlicht!</b>\n\n"
        f"🆔 Auftrag #{task_id} — {pending['title']}\n"
        f"💰 Im Treuhand eingefroren: <b>{gross:.2f} USDT</b>",
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
            "❌ Sitzung abgelaufen. Bitte Auftrag neu erstellen.", reply_markup=MAIN_MENU
        )
        return

    gross = pending["gross"]
    stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
    title_short = pending["title"][:50]

    await context.bot.send_invoice(
        chat_id=user_id,
        title=f"Treuhand: {title_short}",
        description=(
            f"Auftrag auf Fai un Salto veröffentlichen\n"
            f"Treuhandbetrag: {gross:.2f} USDT"
        ),
        payload=f"task_stars_{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Stars für Treuhand", amount=stars_needed)],
        provider_token="",
    )


# ──────────────────────────────────────────────
# Hilfsfunktionen
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
    category = pending.get("category", "🌐 Allgemein")
    deadline = pending.get("deadline", "k.A.")

    channel_text = (
        f"📋 <b>{title}</b> #Auftrag\n\n"
        f"🏷 {category} | 📅 {deadline}\n"
        f"💰 Vergütung: <b>{gross:.2f} USDT</b> (netto: {net:.2f})\n\n"
        f"🆔 Auftrag #{task_id}"
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
        logger.error("Fehler beim Veröffentlichen im Kanal: %s", e)


# ──────────────────────────────────────────────
# Assistent abbrechen
# ──────────────────────────────────────────────

async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Vorgang abgebrochen.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


# ──────────────────────────────────────────────
# Meine Aufträge (Inline-Callback)
# ──────────────────────────────────────────────

async def my_tasks_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tasks = await db.get_user_tasks_as_client(user_id)
    if not tasks:
        await query.message.reply_text("📋 Noch keine Aufträge veröffentlicht.")
        return
    from utils import format_task_summary
    for t in tasks[:10]:
        await query.message.reply_text(format_task_summary(t), parse_mode="HTML")
