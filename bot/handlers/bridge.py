import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from keyboards import main_menu, client_room_kb, executor_room_kb
from utils import is_blocked_file, strip_username_mentions
from strings import STRINGS, DEFAULT_LANG, get_lang
import database as db

logger = logging.getLogger(__name__)


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

    user_id = update.effective_user.id
    session = await db.get_session_by_user(user_id)
    if not session:
        return

    task_id = session["task_id"]
    task = await db.get_task(task_id)
    if not task:
        return

    is_client   = (user_id == session["client_id"])
    is_executor = (user_id == session["executor_id"])
    if not is_client and not is_executor:
        return

    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    recipient_id  = session["executor_id"] if is_client else session["client_id"]
    sender_label  = s["bridge_from_client"] if is_client else s["bridge_from_executor"]

    # Classify media
    if msg.document:
        file_name = msg.document.file_name or ""
        if is_blocked_file(file_name):
            await msg.reply_text(
                s["bridge_file_blocked"].format(name=file_name), parse_mode="HTML"
            )
            return
        msg_type = "document"
        file_id  = msg.document.file_id
        preview  = s["bridge_doc"].format(name=file_name)
    elif msg.photo:
        msg_type = "photo";  file_id = msg.photo[-1].file_id; preview = s["bridge_photo"]
    elif msg.video:
        msg_type = "video";  file_id = msg.video.file_id;     preview = s["bridge_video"]
    elif msg.audio:
        msg_type = "audio";  file_id = msg.audio.file_id;     preview = s["bridge_audio"]
    elif msg.voice:
        msg_type = "voice";  file_id = msg.voice.file_id;     preview = s["bridge_voice"]
    elif msg.sticker:
        msg_type = "sticker";file_id = msg.sticker.file_id;   preview = s["bridge_sticker"]
    elif msg.text:
        msg_type = "text";   file_id = None
        preview  = strip_username_mentions(msg.text[:500])
    else:
        await msg.reply_text(s["bridge_unsupported"])
        return

    await db.log_deal_message(task_id, user_id, msg_type, preview, file_id)

    # Forward in recipient's language for their control panel
    r_lang = await db.get_user_language(recipient_id) or DEFAULT_LANG
    rs = STRINGS[r_lang]
    r_sender_label = rs["bridge_from_client"] if is_client else rs["bridge_from_executor"]

    bot = context.bot
    caption_prefix = r_sender_label + "\n"

    try:
        if msg_type == "text":
            await bot.send_message(chat_id=recipient_id, text=f"{r_sender_label}\n{preview}")
        elif msg_type == "photo":
            await bot.send_photo(chat_id=recipient_id, photo=file_id, caption=caption_prefix + (msg.caption or ""))
        elif msg_type == "document":
            await bot.send_document(chat_id=recipient_id, document=file_id, caption=caption_prefix + (msg.caption or ""))
        elif msg_type == "video":
            await bot.send_video(chat_id=recipient_id, video=file_id, caption=caption_prefix + (msg.caption or ""))
        elif msg_type == "audio":
            await bot.send_audio(chat_id=recipient_id, audio=file_id, caption=caption_prefix + (msg.caption or ""))
        elif msg_type == "voice":
            await bot.send_voice(chat_id=recipient_id, voice=file_id)
        elif msg_type == "sticker":
            await bot.send_sticker(chat_id=recipient_id, sticker=file_id)

        # Floating control panel (sender side, in sender's language)
        if is_client:
            await msg.reply_text(s["bridge_panel"], parse_mode="HTML", reply_markup=client_room_kb(task_id, lang))
        else:
            await msg.reply_text(s["bridge_panel"], parse_mode="HTML", reply_markup=executor_room_kb(task_id, lang))

    except Exception as e:
        logger.error("Forwarding error: %s", e)
        await msg.reply_text(s["bridge_fwd_fail"])


async def complete_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    task_id = int(query.data.split("_", 1)[1])

    task = await db.get_task(task_id)
    if not task or task["client_id"] != user_id:
        await query.answer(s["bridge_not_allowed"], show_alert=True)
        return
    if task["status"] != "in_progress":
        await query.answer(s["bridge_not_active"], show_alert=True)
        return

    ok = await db.release_to_executor(task_id)
    if not ok:
        await query.message.reply_text(s["bridge_release_err"])
        return

    await db.close_deal_session(task_id, "closed")
    task = await db.get_task(task_id)

    await query.message.reply_text(
        s["bridge_confirmed"].format(id=task_id, title=task["title"]),
        parse_mode="HTML",
        reply_markup=main_menu(lang),
    )

    # Notify executor in their language
    exec_lang = await db.get_user_language(task["executor_id"]) or DEFAULT_LANG
    es = STRINGS[exec_lang]
    try:
        await context.bot.send_message(
            chat_id=task["executor_id"],
            text=es["bridge_completed"].format(id=task_id, title=task["title"], net=task["reward_net"]),
            parse_mode="HTML",
            reply_markup=main_menu(exec_lang),
        )
    except Exception as e:
        logger.error("Could not notify executor: %s", e)

    from handlers.rating import prompt_ratings
    await prompt_ratings(context.bot, task_id, task["client_id"], task["executor_id"])
