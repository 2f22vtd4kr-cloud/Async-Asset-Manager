import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    filters,
)

from config import BOT_TOKEN, CRYPTOBOT_TOKEN
from database import init_db, get_user, credit_balance
from utils import setup_logging
from states import (
    TASK_TITLE, TASK_CATEGORY, TASK_DEADLINE, TASK_ATTACHMENTS, TASK_REWARD,
    DIRECT_TARGET, DIRECT_TITLE, DIRECT_CATEGORY, DIRECT_DEADLINE,
    DIRECT_ATTACHMENTS, DIRECT_REWARD,
)

from handlers.common import start, support, my_chats, unknown_command
from handlers.committente import (
    area_committente,
    start_task_wizard,
    task_title_received,
    task_category_received,
    task_deadline_received,
    task_attachment_received,
    task_reward_received,
    cancel_wizard,
    my_tasks_client_callback,
    task_pay_usdt_callback,
    task_pay_stars_callback,
)
from handlers.esecutore import (
    area_esecutore,
    claim_task_callback,
    my_tasks_executor_callback,
)
from handlers.bridge import route_message, complete_task_callback
from handlers.payments import (
    portafoglio,
    topup_crypto_callback,
    topup_stars_callback,
    handle_crypto_amount,
    handle_stars_amount,
    pre_checkout_handler,
    successful_payment_handler,
    prelievo,
)
from handlers.admin import (
    open_dispute_callback,
    admin_release_executor,
    admin_refund_client,
    admin_stats,
)
from handlers.direct import (
    direct_start,
    direct_target_received,
    direct_title_received,
    direct_category_received,
    direct_deadline_received,
    direct_attachment_received,
    direct_reward_received,
    direct_cancel,
    handle_direct_deeplink,
    direct_accept_callback,
    direct_decline_callback,
)
from handlers.rating import rate_executor_callback, rate_client_callback

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"


# ──────────────────────────────────────────────
# CryptoBot invoice poller (background)
# ──────────────────────────────────────────────

async def cryptobot_invoice_poller(app: Application) -> None:
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    processed_ids: set = set()
    logger.info("CryptoBot poller started.")
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{CRYPTOBOT_API}/getInvoices",
                    headers=headers,
                    params={"asset": "USDT", "status": "paid", "count": 100},
                ) as resp:
                    data = await resp.json()

            if data.get("ok"):
                for inv in data.get("result", {}).get("items", []):
                    inv_id = inv.get("invoice_id")
                    if inv_id in processed_ids:
                        continue
                    processed_ids.add(inv_id)

                    payload = inv.get("payload", "")
                    if not payload.startswith("topup_"):
                        continue

                    parts = payload.split("_")
                    if len(parts) < 2:
                        continue
                    try:
                        telegram_id = int(parts[1])
                    except ValueError:
                        continue

                    amount = float(inv.get("amount", 0))
                    if amount <= 0:
                        continue

                    user = await get_user(telegram_id)
                    if not user:
                        continue

                    await credit_balance(telegram_id, amount)
                    logger.info("CryptoBot topup: %.4f USDT → user %d", amount, telegram_id)

                    try:
                        await app.bot.send_message(
                            chat_id=telegram_id,
                            text=f"✅ <b>Ricarica ricevuta!</b>\n\n💵 <b>{amount:.4f} USDT</b> accreditati al tuo saldo.",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error("CryptoBot poller error: %s", e)

        await asyncio.sleep(15)


# ──────────────────────────────────────────────
# /start — handles normal start and deep links
# ──────────────────────────────────────────────

async def start_router(update: Update, context) -> None:
    args = context.args
    if args and args[0].startswith("direct_"):
        await handle_direct_deeplink(update, context)
    else:
        await start(update, context)


# ──────────────────────────────────────────────
# ConversationHandler: public task wizard
# ──────────────────────────────────────────────

def build_task_wizard() -> ConversationHandler:
    media = filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_task_wizard, pattern="^start_task_wizard$")],
        states={
            TASK_TITLE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, task_title_received)],
            TASK_CATEGORY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, task_category_received)],
            TASK_DEADLINE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, task_deadline_received)],
            TASK_ATTACHMENTS: [MessageHandler((media | filters.TEXT) & ~filters.COMMAND, task_attachment_received)],
            TASK_REWARD:      [MessageHandler(filters.TEXT & ~filters.COMMAND, task_reward_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Abbrechen$"), cancel_wizard),
            CommandHandler("start", start_router),
        ],
        allow_reentry=True,
    )


# ──────────────────────────────────────────────
# ConversationHandler: direct deal wizard
# ──────────────────────────────────────────────

def build_direct_wizard() -> ConversationHandler:
    media = filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🤝 Neues Direktgeschäft$"), direct_start)],
        states={
            DIRECT_TARGET:      [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_target_received)],
            DIRECT_TITLE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_title_received)],
            DIRECT_CATEGORY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_category_received)],
            DIRECT_DEADLINE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_deadline_received)],
            DIRECT_ATTACHMENTS: [MessageHandler((media | filters.TEXT) & ~filters.COMMAND, direct_attachment_received)],
            DIRECT_REWARD:      [MessageHandler(filters.TEXT & ~filters.COMMAND, direct_reward_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Abbrechen$"), direct_cancel),
            CommandHandler("start", start_router),
        ],
        allow_reentry=True,
    )


# ──────────────────────────────────────────────
# Text router: Reply Keyboard + deal proxy
# ──────────────────────────────────────────────

async def text_router(update: Update, context) -> None:
    text = update.message.text

    # Pending top-up input takes priority
    if context.user_data.get("awaiting_crypto_topup"):
        await handle_crypto_amount(update, context)
        return
    if context.user_data.get("awaiting_stars_topup"):
        await handle_stars_amount(update, context)
        return

    if text == "💼 Auftraggeber-Bereich":
        await area_committente(update, context)
    elif text == "🛠️ Auftragnehmer-Bereich":
        await area_esecutore(update, context)
    elif text == "💰 Wallet":
        await portafoglio(update, context)
    elif text == "📂 Meine Chats":
        await my_chats(update, context)
    elif text == "ℹ️ Support":
        await support(update, context)
    else:
        # Check active deal session — route through anonymous proxy
        from database import get_session_by_user
        session = await get_session_by_user(update.effective_user.id)
        if session:
            await route_message(update, context)


# ──────────────────────────────────────────────
# Application init
# ──────────────────────────────────────────────

async def post_init(app: Application) -> None:
    await init_db()
    logger.info("Database initialized.")
    asyncio.create_task(cryptobot_invoice_poller(app))


def main() -> None:
    setup_logging()
    logger.info("🐸 Fai un Salto — avvio...")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ── ConversationHandlers (highest priority) ───────────────────────────
    app.add_handler(build_task_wizard())
    app.add_handler(build_direct_wizard())

    # ── Commands ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",    start_router))
    app.add_handler(CommandHandler("prelievo", prelievo))
    app.add_handler(CommandHandler("stats",    admin_stats))

    # ── Task lifecycle callbacks ──────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(claim_task_callback,       pattern=r"^claim_\d+$"))
    app.add_handler(CallbackQueryHandler(complete_task_callback,    pattern=r"^complete_\d+$"))
    app.add_handler(CallbackQueryHandler(open_dispute_callback,     pattern=r"^dispute_\d+$"))

    # ── Admin dispute resolution ──────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(admin_release_executor,    pattern=r"^adm_exec_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_refund_client,       pattern=r"^adm_client_\d+$"))

    # ── Task payment method ───────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(task_pay_usdt_callback,    pattern="^task_pay_usdt$"))
    app.add_handler(CallbackQueryHandler(task_pay_stars_callback,   pattern="^task_pay_stars$"))

    # ── Wallet top-up ─────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(topup_crypto_callback,     pattern="^topup_crypto$"))
    app.add_handler(CallbackQueryHandler(topup_stars_callback,      pattern="^topup_stars$"))

    # ── My tasks ──────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(my_tasks_client_callback,  pattern="^my_tasks_client$"))
    app.add_handler(CallbackQueryHandler(my_tasks_executor_callback,pattern="^my_tasks_executor$"))

    # ── Direct deal ───────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(direct_accept_callback,    pattern=r"^direct_accept_\d+_\w+$"))
    app.add_handler(CallbackQueryHandler(direct_decline_callback,   pattern=r"^direct_decline_\d+_\w+$"))

    # ── Rating system ─────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(rate_executor_callback,    pattern=r"^rate_exec_\d+_[1-5]$"))
    app.add_handler(CallbackQueryHandler(rate_client_callback,      pattern=r"^rate_client_\d+_[1-5]$"))

    # ── Telegram Stars payments ───────────────────────────────────────────
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # ── Generic text + media router ───────────────────────────────────────
    app.add_handler(
        MessageHandler(
            (
                filters.TEXT
                | filters.Document.ALL
                | filters.PHOTO
                | filters.VIDEO
                | filters.AUDIO
                | filters.VOICE
                | filters.Sticker.ALL
            )
            & ~filters.COMMAND,
            text_router,
        )
    )

    # ── Unknown commands ──────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot in polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
