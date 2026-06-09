import asyncio
import logging
import sys
import os

# Ensure bot/ directory is on the path
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
from database import init_db, get_user, credit_balance, add_admin_fee, DB_PATH
from utils import setup_logging
from states import TASK_TITLE, TASK_CATEGORY, TASK_DEADLINE, TASK_ATTACHMENTS, TASK_REWARD

# Handlers
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
from handlers.miniapp import open_mini_app, web_app_data_handler

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"


# ──────────────────────────────────────────────
# CryptoBot invoice poller (background task)
# ──────────────────────────────────────────────

async def cryptobot_invoice_poller(app: Application) -> None:
    """Poll CryptoBot getInvoices every 15 seconds and credit confirmed payments."""
    import aiosqlite
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
                invoices = data.get("result", {}).get("items", [])
                for inv in invoices:
                    inv_id = inv.get("invoice_id")
                    if inv_id in processed_ids:
                        continue
                    processed_ids.add(inv_id)

                    payload = inv.get("payload", "")
                    if not payload.startswith("topup_"):
                        continue

                    # payload format: topup_{telegram_id}_{uuid}
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

                    # Check if already credited (idempotency via processed_ids in-memory)
                    user = await get_user(telegram_id)
                    if not user:
                        continue

                    await credit_balance(telegram_id, amount)
                    logger.info("CryptoBot topup: credited %.4f USDT to user %d", amount, telegram_id)

                    try:
                        await app.bot.send_message(
                            chat_id=telegram_id,
                            text=(
                                f"✅ <b>Ricarica ricevuta!</b>\n\n"
                                f"💵 <b>{amount:.4f} USDT</b> accreditati al tuo saldo."
                            ),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error("CryptoBot poller error: %s", e)

        await asyncio.sleep(15)


# ──────────────────────────────────────────────
# Conversation handler: task creation wizard
# ──────────────────────────────────────────────

def build_task_wizard() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_task_wizard, pattern="^start_task_wizard$")],
        states={
            TASK_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_title_received)
            ],
            TASK_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_category_received)
            ],
            TASK_DEADLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_deadline_received)
            ],
            TASK_ATTACHMENTS: [
                MessageHandler(
                    (filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.TEXT) & ~filters.COMMAND,
                    task_attachment_received,
                )
            ],
            TASK_REWARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_reward_received)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Annulla$"), cancel_wizard),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )


# ──────────────────────────────────────────────
# Text router: handles menu button presses
# ──────────────────────────────────────────────

async def text_router(update: Update, context) -> None:
    """Routes Reply Keyboard menu button presses."""
    text = update.message.text

    # Block if user is in active deal session (proxy routing takes priority)
    from database import get_session_by_user
    session = await get_session_by_user(update.effective_user.id)

    # Check pending topup states
    if context.user_data.get("awaiting_crypto_topup"):
        await handle_crypto_amount(update, context)
        return
    if context.user_data.get("awaiting_stars_topup"):
        await handle_stars_amount(update, context)
        return

    if text == "💼 Area Committente":
        await area_committente(update, context)
    elif text == "🛠️ Area Esecutore":
        await area_esecutore(update, context)
    elif text == "🤝 Nuovo Affare Diretto":
        await update.message.reply_text(
            "🤝 <b>Nuovo Affare Diretto</b>\n\n"
            "Inserisci lo <b>username Telegram</b> dell'esecutore con cui vuoi lavorare "
            "(es. <code>@mario_rossi</code>):",
            parse_mode="HTML",
        )
        context.user_data["awaiting_direct_target"] = True
    elif text == "💰 Portafoglio":
        await portafoglio(update, context)
    elif text == "📂 I Miei Chat":
        await my_chats(update, context)
    elif text == "🌐 Apri Mini App":
        await open_mini_app(update, context)
    elif text == "ℹ️ Supporto":
        await support(update, context)
    elif session:
        # Active deal: proxy the message
        await route_message(update, context)
    else:
        # Fall through — unknown text
        pass


# ──────────────────────────────────────────────
# Main application assembly
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

    # Task creation wizard (ConversationHandler — must be registered before generic handlers)
    app.add_handler(build_task_wizard())

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("prelievo", prelievo))
    app.add_handler(CommandHandler("stats", admin_stats))

    # Callback queries
    app.add_handler(CallbackQueryHandler(claim_task_callback, pattern=r"^claim_\d+$"))
    app.add_handler(CallbackQueryHandler(complete_task_callback, pattern=r"^complete_\d+$"))
    app.add_handler(CallbackQueryHandler(open_dispute_callback, pattern=r"^dispute_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_release_executor, pattern=r"^adm_exec_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_refund_client, pattern=r"^adm_client_\d+$"))
    app.add_handler(CallbackQueryHandler(topup_crypto_callback, pattern="^topup_crypto$"))
    app.add_handler(CallbackQueryHandler(topup_stars_callback, pattern="^topup_stars$"))
    app.add_handler(CallbackQueryHandler(my_tasks_client_callback, pattern="^my_tasks_client$"))
    app.add_handler(CallbackQueryHandler(my_tasks_executor_callback, pattern="^my_tasks_executor$"))

    # Payments (Telegram Stars)
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # Mini App web_app_data
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    # Generic text router (handles Reply Keyboard + proxy)
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Sticker.ALL)
            & ~filters.COMMAND,
            text_router,
        )
    )

    # Unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot in polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
