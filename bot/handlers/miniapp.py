import json
import logging
from telegram import Update, WebAppInfo
from telegram.ext import ContextTypes
from config import MINI_APP_URL
from keyboards import MAIN_MENU, mini_app_kb
import database as db

logger = logging.getLogger(__name__)


async def open_mini_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message with Web App button."""
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0

    await update.message.reply_text(
        f"🌐 <b>Fai un Salto — Mini App</b>\n\n"
        f"💵 Saldo: <b>{bal:.2f} USDT</b>\n\n"
        "Apri la Mini App per navigare gli incarichi, gestire il profilo e molto altro.",
        parse_mode="HTML",
        reply_markup=mini_app_kb(),
    )


async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming JSON data from the Telegram Mini App via web_app_data."""
    web_app_data = update.message.web_app_data
    if not web_app_data:
        return

    user_id = update.effective_user.id
    raw = web_app_data.data

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("WebApp inviato JSON non valido da %s: %s", user_id, raw[:200])
        await update.message.reply_text("⚠️ Dati Mini App non validi.")
        return

    action = payload.get("action", "")
    logger.info("WebApp action '%s' da utente %s", action, user_id)

    if action == "sync_profile":
        # Profile synchronization
        user = await db.get_user(user_id)
        if user:
            resp = {
                "balance_usdt": user["balance_usdt"],
                "frozen_usdt": user["frozen_usdt"],
                "client_rating": user["client_rating"],
                "executor_rating": user["executor_rating"],
                "total_tasks_client": user["total_tasks_client"],
                "total_tasks_executor": user["total_tasks_executor"],
            }
            await update.message.reply_text(
                f"🔄 <b>Profilo sincronizzato</b>\n\n"
                f"💵 Saldo: {user['balance_usdt']:.2f} USDT\n"
                f"⭐ Rating committente: {user['client_rating']:.1f}\n"
                f"⭐ Rating esecutore: {user['executor_rating']:.1f}",
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )

    elif action == "browse_tasks":
        # Job browsing action from Mini App
        category = payload.get("category", None)
        import aiosqlite
        from database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            if category:
                async with conn.execute(
                    "SELECT * FROM tasks WHERE status='open' AND category=? ORDER BY created_at DESC LIMIT 5",
                    (category,),
                ) as cursor:
                    tasks = [dict(r) for r in await cursor.fetchall()]
            else:
                async with conn.execute(
                    "SELECT * FROM tasks WHERE status='open' ORDER BY created_at DESC LIMIT 5"
                ) as cursor:
                    tasks = [dict(r) for r in await cursor.fetchall()]

        if tasks:
            for t in tasks:
                from utils import format_task_summary
                await update.message.reply_text(format_task_summary(t), parse_mode="HTML")
        else:
            await update.message.reply_text("📋 Nessun incarico disponibile al momento.")

    elif action == "wallet_telemetry":
        # Wallet telemetry display from Mini App
        user = await db.get_user(user_id)
        if user:
            await update.message.reply_text(
                f"💰 <b>Telemetria Portafoglio</b>\n\n"
                f"Disponibile: {user['balance_usdt']:.4f} USDT\n"
                f"In escrow: {user['frozen_usdt']:.4f} USDT\n"
                f"Totale: {user['balance_usdt'] + user['frozen_usdt']:.4f} USDT",
                parse_mode="HTML",
            )

    else:
        logger.info("Azione Mini App non gestita: %s", action)
        await update.message.reply_text(
            f"📡 Dati ricevuti dalla Mini App.\nAzione: <code>{action}</code>",
            parse_mode="HTML",
        )
