import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from keyboards import MAIN_MENU, client_room_kb, executor_room_kb
from utils import is_blocked_file, strip_username_mentions
import database as db

logger = logging.getLogger(__name__)

BLOCKED_TYPES = {"application/x-msdownload", "application/x-sh", "application/x-bat"}


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main proxy router: intercepts messages and forwards them anonymously."""
    msg = update.message
    if not msg:
        return

    user_id = update.effective_user.id
    session = await db.get_session_by_user(user_id)
    if not session:
        return  # Not in an active deal — fall through to other handlers

    task_id = session["task_id"]
    task = await db.get_task(task_id)
    if not task:
        return

    is_client = (user_id == session["client_id"])
    is_executor = (user_id == session["executor_id"])

    if not is_client and not is_executor:
        return

    recipient_id = session["executor_id"] if is_client else session["client_id"]
    sender_label = "📩 Nachricht vom Auftraggeber:" if is_client else "📩 Nachricht vom Auftragnehmer:"

    # Block dangerous file types
    if msg.document:
        file_name = msg.document.file_name or ""
        if is_blocked_file(file_name):
            await msg.reply_text(
                f"🚫 Datei <code>{file_name}</code> aus Sicherheitsgründen gesperrt.",
                parse_mode="HTML",
            )
            return
        msg_type = "document"
        file_id = msg.document.file_id
        preview = f"[Dokument: {file_name}]"
    elif msg.photo:
        msg_type = "photo"
        file_id = msg.photo[-1].file_id
        preview = "[Foto]"
    elif msg.video:
        msg_type = "video"
        file_id = msg.video.file_id
        preview = "[Video]"
    elif msg.audio:
        msg_type = "audio"
        file_id = msg.audio.file_id
        preview = "[Audio]"
    elif msg.voice:
        msg_type = "voice"
        file_id = msg.voice.file_id
        preview = "[Sprachnachricht]"
    elif msg.sticker:
        msg_type = "sticker"
        file_id = msg.sticker.file_id
        preview = "[Sticker]"
    elif msg.text:
        msg_type = "text"
        file_id = None
        preview = strip_username_mentions(msg.text[:500])
    else:
        await msg.reply_text("⚠️ Nachrichtentyp nicht unterstützt.")
        return

    # Log message
    await db.log_deal_message(task_id, user_id, msg_type, preview, file_id)

    # Forward anonymously with copy_message
    bot = context.bot
    caption_prefix = sender_label + "\n"

    try:
        if msg_type == "text":
            await bot.send_message(
                chat_id=recipient_id,
                text=f"{sender_label}\n{preview}",
            )
        elif msg_type == "photo":
            await bot.send_photo(
                chat_id=recipient_id,
                photo=file_id,
                caption=caption_prefix + (msg.caption or ""),
            )
        elif msg_type == "document":
            await bot.send_document(
                chat_id=recipient_id,
                document=file_id,
                caption=caption_prefix + (msg.caption or ""),
            )
        elif msg_type == "video":
            await bot.send_video(
                chat_id=recipient_id,
                video=file_id,
                caption=caption_prefix + (msg.caption or ""),
            )
        elif msg_type == "audio":
            await bot.send_audio(
                chat_id=recipient_id,
                audio=file_id,
                caption=caption_prefix + (msg.caption or ""),
            )
        elif msg_type == "voice":
            await bot.send_voice(chat_id=recipient_id, voice=file_id)
        elif msg_type == "sticker":
            await bot.send_sticker(chat_id=recipient_id, sticker=file_id)

        # Re-send floating control panel after each message
        if is_client:
            await msg.reply_text(
                "🎛 <b>Steuerfeld</b>",
                parse_mode="HTML",
                reply_markup=client_room_kb(task_id),
            )
        else:
            await msg.reply_text(
                "🎛 <b>Steuerfeld</b>",
                parse_mode="HTML",
                reply_markup=executor_room_kb(task_id),
            )

    except Exception as e:
        logger.error("Fehler beim Weiterleiten der Nachricht: %s", e)
        await msg.reply_text("⚠️ Fehler beim Weiterleiten der Nachricht. Bitte erneut versuchen.")


async def complete_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Client confirms task completion — triggers 90/10 escrow release."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    task_id = int(query.data.split("_", 1)[1])

    task = await db.get_task(task_id)
    if not task or task["client_id"] != user_id:
        await query.answer("❌ Vorgang nicht erlaubt.", show_alert=True)
        return

    if task["status"] != "in_progress":
        await query.answer("⚠️ Dieser Deal ist nicht aktiv.", show_alert=True)
        return

    ok = await db.release_to_executor(task_id)
    if not ok:
        await query.message.reply_text("❌ Fehler bei der Freigabe der Mittel. Bitte Support kontaktieren.")
        return

    await db.close_deal_session(task_id, "closed")
    task = await db.get_task(task_id)

    bot = context.bot
    await query.message.reply_text(
        f"✅ <b>Abschluss bestätigt!</b>\n\n"
        f"Auftrag #{task_id} — {task['title']}\n"
        f"Die Vergütung wurde an den Auftragnehmer freigegeben.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )
    try:
        await bot.send_message(
            chat_id=task["executor_id"],
            text=(
                f"🎉 <b>Auftrag abgeschlossen!</b>\n\n"
                f"Auftrag #{task_id} — {task['title']}\n"
                f"💰 <b>{task['reward_net']:.2f} USDT</b> wurden deinem Guthaben gutgeschrieben."
            ),
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
    except Exception as e:
        logger.error("Auftragnehmer konnte nicht benachrichtigt werden: %s", e)

    # Prompt both parties to rate each other
    from handlers.rating import prompt_ratings
    await prompt_ratings(bot, task_id, task["client_id"], task["executor_id"])
