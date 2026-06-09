import logging
import uuid
import aiohttp
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes, ConversationHandler, PreCheckoutQueryHandler
from config import CRYPTOBOT_TOKEN, STAR_TO_USDT_RATE, PLATFORM_FEE_RATE
from keyboards import MAIN_MENU, topup_method_kb
from utils import validate_reward, calc_stars_for_usdt
import database as db

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"


# ──────────────────────────────────────────────
# Wallet dashboard
# ──────────────────────────────────────────────

async def portafoglio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await db.get_or_create_user(user_id, update.effective_user.username)
    text = (
        "💰 <b>Portafoglio</b>\n\n"
        f"💵 Saldo disponibile: <b>{user['balance_usdt']:.2f} USDT</b>\n"
        f"🔒 In escrow: <b>{user['frozen_usdt']:.2f} USDT</b>\n\n"
        "Scegli un metodo di ricarica:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=topup_method_kb())


# ──────────────────────────────────────────────
# Top-up Track A: CryptoBot
# ──────────────────────────────────────────────

async def topup_crypto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💳 <b>Ricarica via CryptoBot (USDT)</b>\n\n"
        "Inserisci l'importo in USDT che vuoi ricaricare (es. <code>10.00</code>):",
        parse_mode="HTML",
    )
    context.user_data["awaiting_crypto_topup"] = True


async def handle_crypto_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_crypto_topup"):
        return

    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(
            "⚠️ Importo non valido. Inserisci un numero positivo (es. <code>10.00</code>):",
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
        "description": f"Ricarica Fai un Salto — {amount} USDT",
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
            invoice = data["result"]
            pay_url = invoice["pay_url"]
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("💳 Paga via CryptoBot P2P", url=pay_url)]]
            )
            await update.message.reply_text(
                f"✅ Fattura creata per <b>{amount:.2f} USDT</b>\n\n"
                "Clicca il pulsante per completare il pagamento.\n"
                "Il saldo verrà aggiornato automaticamente dopo la conferma.",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            logger.error("CryptoBot createInvoice error: %s", data)
            await update.message.reply_text(
                "❌ Errore nella creazione della fattura CryptoBot. Riprova più tardi."
            )
    except Exception as e:
        logger.error("CryptoBot request failed: %s", e)
        await update.message.reply_text("⚠️ Errore di connessione con CryptoBot. Riprova.")


# ──────────────────────────────────────────────
# Top-up Track B: Telegram Stars (XTR)
# ──────────────────────────────────────────────

async def topup_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "⭐ <b>Ricarica via Telegram Stars</b>\n\n"
        f"Tasso di conversione: 1 Star = {STAR_TO_USDT_RATE} USDT\n\n"
        "Inserisci l'importo in USDT che vuoi ricaricare (es. <code>5.00</code>):",
        parse_mode="HTML",
    )
    context.user_data["awaiting_stars_topup"] = True


async def handle_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_stars_topup"):
        return

    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(
            "⚠️ Importo non valido. Inserisci un numero positivo (es. <code>5.00</code>):",
            parse_mode="HTML",
        )
        return

    context.user_data.pop("awaiting_stars_topup", None)
    stars_needed = calc_stars_for_usdt(amount, STAR_TO_USDT_RATE)
    user_id = update.effective_user.id

    context.user_data["pending_stars_usdt"] = amount

    await context.bot.send_invoice(
        chat_id=user_id,
        title="Ricarica Portafoglio",
        description=f"Ricarica {amount:.2f} USDT su Fai un Salto (10% fee inclusa)",
        payload=f"stars_topup_{user_id}_{amount}",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=stars_needed)],
        provider_token="",
    )


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    stars_paid = payment.total_amount

    gross_usdt = round(stars_paid * STAR_TO_USDT_RATE, 8)
    platform_fee = round(gross_usdt * PLATFORM_FEE_RATE, 8)
    net_credit = round(gross_usdt - platform_fee, 8)

    await db.credit_balance(user_id, net_credit)
    await db.add_admin_fee(platform_fee)

    await update.message.reply_text(
        f"⭐ <b>Ricarica completata!</b>\n\n"
        f"Stars pagati: {stars_paid}\n"
        f"Valore lordo: {gross_usdt:.4f} USDT\n"
        f"Commissione piattaforma (10%): -{platform_fee:.4f} USDT\n"
        f"💵 <b>Accreditato: {net_credit:.4f} USDT</b>",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )


# ──────────────────────────────────────────────
# Withdrawal: /prelievo <amount>
# ──────────────────────────────────────────────

async def prelievo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "💸 <b>Prelievo</b>\n\nUso: <code>/prelievo &lt;importo&gt;</code>\n"
            "Es: <code>/prelievo 10.00</code>",
            parse_mode="HTML",
        )
        return

    amount = validate_reward(args[0])
    if not amount:
        await update.message.reply_text(
            "⚠️ Importo non valido. Usa: <code>/prelievo 10.00</code>",
            parse_mode="HTML",
        )
        return

    user = await db.get_user(user_id)
    if not user or user["balance_usdt"] < amount:
        bal = user["balance_usdt"] if user else 0.0
        await update.message.reply_text(
            f"❌ Saldo insufficiente. Disponibile: <b>{bal:.2f} USDT</b>, "
            f"richiesto: <b>{amount:.2f} USDT</b>.",
            parse_mode="HTML",
        )
        return

    # Atomically debit first
    ok = await db.debit_balance(user_id, amount)
    if not ok:
        await update.message.reply_text("❌ Errore nella transazione. Riprova.")
        return

    spend_id = str(uuid.uuid4())
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    body = {
        "user_id": user_id,
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": spend_id,
        "comment": "Prelievo Fai un Salto",
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
                f"✅ <b>Prelievo confermato!</b>\n\n"
                f"💸 <b>{amount:.2f} USDT</b> trasferiti al tuo wallet CryptoBot.",
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
        else:
            raise Exception(f"CryptoBot transfer failed: {data}")

    except Exception as e:
        logger.error("Prelievo fallito: %s", e)
        # Rollback: restore funds
        await db.credit_balance(user_id, amount)
        await update.message.reply_text(
            "⚠️ Errore di rete CryptoBot. L'importo è stato riaccreditato al tuo saldo interno.",
            reply_markup=MAIN_MENU,
        )
