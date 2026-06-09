import logging
import uuid
import aiohttp
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes, PreCheckoutQueryHandler
from config import CRYPTOBOT_TOKEN, STAR_TO_USDT_RATE, PLATFORM_FEE_RATE
from keyboards import MAIN_MENU, topup_method_kb
from utils import validate_reward, calc_stars_for_usdt
import database as db

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"


# ──────────────────────────────────────────────
# Wallet-Dashboard
# ──────────────────────────────────────────────

async def portafoglio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await db.get_or_create_user(user_id, update.effective_user.username)
    text = (
        "💰 <b>Wallet</b>\n\n"
        f"💵 Verfügbares Guthaben: <b>{user['balance_usdt']:.2f} USDT</b>\n"
        f"🔒 Im Treuhand: <b>{user['frozen_usdt']:.2f} USDT</b>\n\n"
        "Aufladen oder auszahlen:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=topup_method_kb())


# ──────────────────────────────────────────────
# Aufladung Methode A: CryptoBot (USDT)
# ──────────────────────────────────────────────

async def topup_crypto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💳 <b>Aufladen via CryptoBot (USDT)</b>\n\n"
        "Gib den USDT-Betrag ein, den du aufladen möchtest (z.B. <code>10.00</code>):",
        parse_mode="HTML",
    )
    context.user_data["awaiting_crypto_topup"] = True


async def handle_crypto_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(
            "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>10.00</code>):",
            parse_mode="HTML",
        )
        return

    user_id = update.effective_user.id
    context.user_data.pop("awaiting_crypto_topup", None)

    payload = f"topup_{user_id}_{uuid.uuid4().hex[:8]}"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    body = {
        "asset": "USDT",
        "amount": str(amount),
        "payload": payload,
        "description": f"Aufladung Fai un Salto — {amount} USDT",
        "allow_comments": False,
        "allow_anonymous": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTOBOT_API}/createInvoice", headers=headers, json=body
            ) as resp:
                data = await resp.json()

        if data.get("ok"):
            pay_url = data["result"]["pay_url"]
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("💳 Zahlen via CryptoBot P2P", url=pay_url)]]
            )
            await update.message.reply_text(
                f"✅ Rechnung für <b>{amount:.2f} USDT</b> erstellt\n\n"
                "Klicke den Button, um die Zahlung abzuschließen.\n"
                "Das Guthaben wird nach Bestätigung automatisch aktualisiert.",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            logger.error("CryptoBot createInvoice error: %s", data)
            await update.message.reply_text(
                "❌ Fehler beim Erstellen der CryptoBot-Rechnung. Bitte später erneut versuchen."
            )
    except Exception as e:
        logger.error("CryptoBot request failed: %s", e)
        await update.message.reply_text("⚠️ Verbindungsfehler mit CryptoBot. Bitte erneut versuchen.")


# ──────────────────────────────────────────────
# Aufladung Methode B: Telegram Stars (XTR)
# ──────────────────────────────────────────────

async def topup_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "⭐ <b>Guthaben via Telegram Stars aufladen</b>\n\n"
        f"Kurs: 1 Star = {STAR_TO_USDT_RATE} USDT\n"
        "⚠️ Es gilt eine Plattformgebühr von 10% auf die Aufladung.\n\n"
        "Gib den USDT-Betrag ein, den du aufladen möchtest (z.B. <code>5.00</code>):",
        parse_mode="HTML",
    )
    context.user_data["awaiting_stars_topup"] = True


async def handle_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(
            "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>5.00</code>):",
            parse_mode="HTML",
        )
        return

    context.user_data.pop("awaiting_stars_topup", None)
    user_id = update.effective_user.id
    stars_needed = calc_stars_for_usdt(amount, STAR_TO_USDT_RATE)

    await context.bot.send_invoice(
        chat_id=user_id,
        title="Wallet-Guthaben aufladen",
        description=f"{amount:.2f} USDT auf Fai un Salto aufladen (inkl. 10% Gebühr)",
        payload=f"stars_topup_{user_id}_{amount}",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=stars_needed)],
        provider_token="",
    )


# ──────────────────────────────────────────────
# Pre-Checkout-Handler (für alle Stars-Zahlungen erforderlich)
# ──────────────────────────────────────────────

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


# ──────────────────────────────────────────────
# Erfolgreiche Zahlung
# ──────────────────────────────────────────────

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    stars_paid = payment.total_amount
    payload = payment.invoice_payload

    # ── Treuhand-Zahlung via Stars ──────────────────────────────────────────
    if payload.startswith("task_stars_"):
        pending = context.user_data.get("pending_task")
        if not pending:
            await update.message.reply_text(
                "⚠️ Auftragsdaten nicht gefunden. Deine Stars sind sicher — bitte Support kontaktieren.",
                reply_markup=MAIN_MENU,
            )
            return

        gross = pending["gross"]

        import aiosqlite
        from database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("BEGIN")
            cursor = await conn.execute(
                "INSERT INTO tasks "
                "(client_id, title, description, deadline, category, attachments, reward_gross, reward_net, status) "
                "VALUES (?,?,?,?,?,?,?,?,'open')",
                (
                    user_id,
                    pending["title"],
                    pending["title"],
                    pending["deadline"],
                    pending["category"],
                    pending["attachments"],
                    gross,
                    pending["net"],
                ),
            )
            task_id = cursor.lastrowid
            await conn.execute(
                "UPDATE users SET frozen_usdt = frozen_usdt + ?, "
                "total_tasks_client = total_tasks_client + 1 WHERE telegram_id = ?",
                (gross, user_id),
            )
            await conn.execute("COMMIT")

        context.user_data.pop("pending_task", None)

        from handlers.committente import _post_to_channel
        await _post_to_channel(update.get_bot(), task_id, pending)

        await update.message.reply_text(
            f"⭐ <b>Stars-Zahlung bestätigt!</b>\n\n"
            f"🆔 Auftrag #{task_id} — {pending['title']}\n"
            f"⭐ Gezahlte Stars: <b>{stars_paid}</b>\n"
            f"💰 Treuhand eingefroren: <b>{gross:.2f} USDT</b>\n\n"
            "Der Auftrag ist jetzt im Kanal sichtbar.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return

    # ── Allgemeine Stars-Guthabenaufladung ─────────────────────────────────
    if payload.startswith("stars_topup_"):
        gross_usdt = round(stars_paid * STAR_TO_USDT_RATE, 8)
        platform_fee = round(gross_usdt * PLATFORM_FEE_RATE, 8)
        net_credit = round(gross_usdt - platform_fee, 8)

        await db.credit_balance(user_id, net_credit)
        await db.add_admin_fee(platform_fee)

        await update.message.reply_text(
            f"⭐ <b>Aufladung abgeschlossen!</b>\n\n"
            f"Gezahlte Stars: <b>{stars_paid}</b>\n"
            f"Bruttowert: {gross_usdt:.4f} USDT\n"
            f"Gebühr (10%): -{platform_fee:.4f} USDT\n"
            f"💵 <b>Gutgeschrieben: {net_credit:.4f} USDT</b>",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return

    logger.warning("Successful payment with unknown payload: %s", payload)


# ──────────────────────────────────────────────
# Auszahlung: /auszahlung <betrag>
# ──────────────────────────────────────────────

async def prelievo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "💸 <b>Auszahlung</b>\n\nVerwendung: <code>/prelievo &lt;Betrag&gt;</code>\n"
            "Bsp: <code>/prelievo 10.00</code>",
            parse_mode="HTML",
        )
        return

    amount = validate_reward(args[0])
    if not amount:
        await update.message.reply_text(
            "⚠️ Ungültiger Betrag. Verwende: <code>/prelievo 10.00</code>",
            parse_mode="HTML",
        )
        return

    user = await db.get_user(user_id)
    if not user or user["balance_usdt"] < amount:
        bal = user["balance_usdt"] if user else 0.0
        await update.message.reply_text(
            f"❌ Unzureichendes Guthaben. Verfügbar: <b>{bal:.2f} USDT</b>, "
            f"angefordert: <b>{amount:.2f} USDT</b>.",
            parse_mode="HTML",
        )
        return

    ok = await db.debit_balance(user_id, amount)
    if not ok:
        await update.message.reply_text("❌ Transaktionsfehler. Bitte erneut versuchen.")
        return

    spend_id = str(uuid.uuid4())
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    body = {
        "user_id": user_id,
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": spend_id,
        "comment": "Auszahlung Fai un Salto",
        "disable_send_notification": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTOBOT_API}/transfer", headers=headers, json=body
            ) as resp:
                data = await resp.json()

        if data.get("ok"):
            await update.message.reply_text(
                f"✅ <b>Auszahlung bestätigt!</b>\n\n"
                f"💸 <b>{amount:.2f} USDT</b> an dein CryptoBot-Wallet überwiesen.",
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
        else:
            raise Exception(f"CryptoBot transfer failed: {data}")

    except Exception as e:
        logger.error("Auszahlung fehlgeschlagen: %s", e)
        await db.credit_balance(user_id, amount)
        await update.message.reply_text(
            "⚠️ CryptoBot-Netzwerkfehler. Der Betrag wurde deinem internen Guthaben zurückgebucht.",
            reply_markup=MAIN_MENU,
        )
