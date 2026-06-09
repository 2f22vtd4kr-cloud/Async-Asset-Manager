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
# Wallet dashboard
# ──────────────────────────────────────────────

async def portafoglio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await db.get_or_create_user(user_id, update.effective_user.username)
    text = (
        "💰 <b>Portafoglio</b>\n\n"
        f"💵 Saldo disponibile: <b>{user['balance_usdt']:.2f} USDT</b>\n"
        f"🔒 In escrow: <b>{user['frozen_usdt']:.2f} USDT</b>\n\n"
        "Ricarica o preleva:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=topup_method_kb())


# ──────────────────────────────────────────────
# Top-up Track A: CryptoBot (USDT)
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
            pay_url = data["result"]["pay_url"]
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
# Top-up Track B: Telegram Stars (XTR) — balance top-up
# ──────────────────────────────────────────────

async def topup_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "⭐ <b>Ricarica Saldo via Telegram Stars</b>\n\n"
        f"Tasso: 1 Star = {STAR_TO_USDT_RATE} USDT\n"
        "⚠️ Commissione piattaforma 10% applicata alla ricarica.\n\n"
        "Inserisci l'importo in USDT che vuoi ricaricare (es. <code>5.00</code>):",
        parse_mode="HTML",
    )
    context.user_data["awaiting_stars_topup"] = True


async def handle_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(
            "⚠️ Importo non valido. Inserisci un numero positivo (es. <code>5.00</code>):",
            parse_mode="HTML",
        )
        return

    context.user_data.pop("awaiting_stars_topup", None)
    user_id = update.effective_user.id
    stars_needed = calc_stars_for_usdt(amount, STAR_TO_USDT_RATE)

    await context.bot.send_invoice(
        chat_id=user_id,
        title="Ricarica Saldo Portafoglio",
        description=f"Ricarica {amount:.2f} USDT su Fai un Salto (10% fee inclusa)",
        payload=f"stars_topup_{user_id}_{amount}",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=stars_needed)],
        provider_token="",
    )


# ──────────────────────────────────────────────
# Pre-checkout handler (required for all Stars payments)
# ──────────────────────────────────────────────

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


# ──────────────────────────────────────────────
# Successful payment dispatcher
# ──────────────────────────────────────────────

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    stars_paid = payment.total_amount
    payload = payment.invoice_payload

    # ── Task escrow payment via Stars ──────────────────────────────────────
    if payload.startswith("task_stars_"):
        pending = context.user_data.get("pending_task")
        if not pending:
            await update.message.reply_text(
                "⚠️ Dati incarico non trovati. I tuoi Stars sono al sicuro — contatta il supporto.",
                reply_markup=MAIN_MENU,
            )
            return

        gross = pending["gross"]

        # Create task and freeze funds directly (Stars already paid externally)
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
            # Freeze directly without touching balance (Stars bypassed deposit)
            await conn.execute(
                "UPDATE users SET frozen_usdt = frozen_usdt + ?, "
                "total_tasks_client = total_tasks_client + 1 WHERE telegram_id = ?",
                (gross, user_id),
            )
            await conn.execute("COMMIT")

        context.user_data.pop("pending_task", None)

        # Post to channel
        from handlers.committente import _post_to_channel
        await _post_to_channel(update.get_bot(), task_id, pending)

        await update.message.reply_text(
            f"⭐ <b>Pagamento Stars confermato!</b>\n\n"
            f"🆔 Task #{task_id} — {pending['title']}\n"
            f"⭐ Stars pagati: <b>{stars_paid}</b>\n"
            f"💰 Escrow bloccato: <b>{gross:.2f} USDT</b>\n\n"
            "L'incarico è ora visibile sul canale.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return

    # ── General Stars balance top-up ───────────────────────────────────────
    if payload.startswith("stars_topup_"):
        gross_usdt = round(stars_paid * STAR_TO_USDT_RATE, 8)
        platform_fee = round(gross_usdt * PLATFORM_FEE_RATE, 8)
        net_credit = round(gross_usdt - platform_fee, 8)

        await db.credit_balance(user_id, net_credit)
        await db.add_admin_fee(platform_fee)

        await update.message.reply_text(
            f"⭐ <b>Ricarica completata!</b>\n\n"
            f"Stars pagati: <b>{stars_paid}</b>\n"
            f"Valore lordo: {gross_usdt:.4f} USDT\n"
            f"Commissione (10%): -{platform_fee:.4f} USDT\n"
            f"💵 <b>Accreditato: {net_credit:.4f} USDT</b>",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
        return

    logger.warning("Successful payment with unknown payload: %s", payload)


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
        await db.credit_balance(user_id, amount)
        await update.message.reply_text(
            "⚠️ Errore di rete CryptoBot. L'importo è stato riaccreditato al tuo saldo interno.",
            reply_markup=MAIN_MENU,
        )
