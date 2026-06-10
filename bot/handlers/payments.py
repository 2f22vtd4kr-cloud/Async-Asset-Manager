import logging
import uuid
import aiohttp
from telegram import Update, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, PreCheckoutQueryHandler
from config import CRYPTOBOT_TOKEN, STAR_TO_USDT_RATE, PLATFORM_FEE_RATE
from keyboards import main_menu, topup_method_kb
from utils import validate_reward, calc_stars_for_usdt
from strings import STRINGS, DEFAULT_LANG, get_lang
import database as db

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"


async def portafoglio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    user = await db.get_or_create_user(user_id, update.effective_user.username)
    text = (
        f"{s['wallet_hdr']}\n\n"
        f"{s['wallet_avail']}: <b>{user['balance_usdt']:.2f} USDT</b>\n"
        f"{s['wallet_frozen']}: <b>{user['frozen_usdt']:.2f} USDT</b>\n\n"
        f"{s['wallet_action']}"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=topup_method_kb(lang))


async def topup_crypto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    await query.message.reply_text(s["topup_crypto_prompt"], parse_mode="HTML")
    context.user_data["awaiting_crypto_topup"] = True


async def handle_crypto_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(s["topup_amount_err"], parse_mode="HTML")
        return

    context.user_data.pop("awaiting_crypto_topup", None)
    payload = f"topup_{user_id}_{uuid.uuid4().hex[:8]}"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    body = {
        "asset": "USDT",
        "amount": str(amount),
        "payload": payload,
        "description": s["topup_crypto_desc"].format(amount=amount),
        "allow_comments": False,
        "allow_anonymous": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{CRYPTOBOT_API}/createInvoice", headers=headers, json=body) as resp:
                data = await resp.json()
        if data.get("ok"):
            pay_url = data["result"]["pay_url"]
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(s["topup_pay_btn"], url=pay_url)]])
            await update.message.reply_text(
                s["topup_invoice_ok"].format(amount=amount),
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            logger.error("CryptoBot createInvoice error: %s", data)
            await update.message.reply_text(s["topup_cryptobot_err"])
    except Exception as e:
        logger.error("CryptoBot request failed: %s", e)
        await update.message.reply_text(s["topup_conn_err"])


async def topup_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    await query.message.reply_text(
        s["topup_stars_prompt"].format(rate=STAR_TO_USDT_RATE),
        parse_mode="HTML",
    )
    context.user_data["awaiting_stars_topup"] = True


async def handle_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    amount = validate_reward(update.message.text)
    if not amount:
        await update.message.reply_text(s["topup_amount_err"], parse_mode="HTML")
        return

    context.user_data.pop("awaiting_stars_topup", None)
    stars_needed = calc_stars_for_usdt(amount, STAR_TO_USDT_RATE)

    await context.bot.send_invoice(
        chat_id=user_id,
        title=s["topup_stars_title"],
        description=s["topup_stars_desc"].format(amount=amount),
        payload=f"stars_topup_{user_id}_{amount}",
        currency="XTR",
        prices=[LabeledPrice(label=s["topup_stars_label"], amount=stars_needed)],
        provider_token="",
    )


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment   = update.message.successful_payment
    user_id   = update.effective_user.id
    stars_paid = payment.total_amount
    payload   = payment.invoice_payload
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    if payload.startswith("task_stars_"):
        pending = context.user_data.get("pending_task")
        if not pending:
            await update.message.reply_text(s["stars_task_missing"], reply_markup=main_menu(lang))
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
                (user_id, pending["title"], pending["title"], pending["deadline"],
                 pending["category"], pending["attachments"], gross, pending["net"]),
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
        await _post_to_channel(update.get_bot(), task_id, pending, lang)

        await update.message.reply_text(
            s["stars_task_ok"].format(id=task_id, title=pending["title"], stars=stars_paid, gross=gross),
            parse_mode="HTML",
            reply_markup=main_menu(lang),
        )
        return

    if payload.startswith("stars_topup_"):
        gross_usdt   = round(stars_paid * STAR_TO_USDT_RATE, 8)
        platform_fee = round(gross_usdt * PLATFORM_FEE_RATE, 8)
        net_credit   = round(gross_usdt - platform_fee, 8)

        await db.credit_balance(user_id, net_credit)
        await db.add_admin_fee(platform_fee)

        await update.message.reply_text(
            s["stars_topup_ok"].format(stars=stars_paid, gross=gross_usdt, fee=platform_fee, net=net_credit),
            parse_mode="HTML",
            reply_markup=main_menu(lang),
        )
        return

    logger.warning("Successful payment with unknown payload: %s", payload)


async def prelievo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    args = context.args

    if not args:
        await update.message.reply_text(s["withdrawal_hdr"], parse_mode="HTML")
        return

    amount = validate_reward(args[0])
    if not amount:
        await update.message.reply_text(s["withdrawal_inv"], parse_mode="HTML")
        return

    user = await db.get_user(user_id)
    if not user or user["balance_usdt"] < amount:
        bal = user["balance_usdt"] if user else 0.0
        await update.message.reply_text(
            s["withdrawal_insuf"].format(bal=bal, amount=amount), parse_mode="HTML"
        )
        return

    ok = await db.debit_balance(user_id, amount)
    if not ok:
        await update.message.reply_text(s["withdrawal_tx_err"])
        return

    spend_id = str(uuid.uuid4())
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    body = {
        "user_id": user_id,
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": spend_id,
        "comment": s["withdrawal_comment"],
        "disable_send_notification": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{CRYPTOBOT_API}/transfer", headers=headers, json=body) as resp:
                data = await resp.json()
        if data.get("ok"):
            await update.message.reply_text(
                s["withdrawal_ok"].format(amount=amount),
                parse_mode="HTML",
                reply_markup=main_menu(lang),
            )
        else:
            raise Exception(f"CryptoBot transfer failed: {data}")
    except Exception as e:
        logger.error("Withdrawal failed: %s", e)
        await db.credit_balance(user_id, amount)
        await update.message.reply_text(s["withdrawal_net_err"], reply_markup=main_menu(lang))
