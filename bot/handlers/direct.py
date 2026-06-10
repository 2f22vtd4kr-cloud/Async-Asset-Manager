"""
Direct Deal flow — private invite-only task between a specific client and executor.
"""
import json
import logging
import uuid

import aiosqlite
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import PLATFORM_FEE_RATE
from database import DB_PATH, freeze_funds, get_user, refund_client, create_deal_session
from keyboards import (
    cancel_kb, category_kb, main_menu,
    client_room_kb, direct_deal_offer_kb, executor_room_kb,
    skip_attachments_kb,
)
from states import (
    DIRECT_ATTACHMENTS, DIRECT_CATEGORY, DIRECT_DEADLINE,
    DIRECT_REWARD, DIRECT_TARGET, DIRECT_TITLE,
)
from utils import calc_net_reward, is_blocked_file, validate_reward
from strings import STRINGS, DEFAULT_LANG, get_lang, all_cancel_texts, all_skip_texts

logger = logging.getLogger(__name__)
TOKEN_LEN = 12


async def direct_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    context.user_data["attachments"] = []
    await update.message.reply_text(s["direct_start"], parse_mode="HTML", reply_markup=cancel_kb(lang))
    return DIRECT_TARGET


async def direct_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    if text in all_cancel_texts():
        return await direct_cancel(update, context)

    raw = text.strip()
    username = raw if raw.startswith("@") else f"@{raw}"
    if len(username) < 2 or not username[1:].replace("_", "").isalnum():
        await update.message.reply_text(s["direct_username_err"], parse_mode="HTML", reply_markup=cancel_kb(lang))
        return DIRECT_TARGET

    context.user_data["direct_target"] = username
    await update.message.reply_text(
        s["direct_exec_selected"].format(username=username) + "\n\n" + s["direct_step1"],
        parse_mode="HTML",
        reply_markup=cancel_kb(lang),
    )
    return DIRECT_TITLE


async def direct_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    if text in all_cancel_texts():
        return await direct_cancel(update, context)

    title = text.strip()
    if len(title) < 5 or len(title) > 200:
        await update.message.reply_text(s["direct_title_err"], reply_markup=cancel_kb(lang))
        return DIRECT_TITLE

    context.user_data["title"] = title
    await update.message.reply_text(s["direct_step2"], parse_mode="HTML", reply_markup=category_kb(lang))
    return DIRECT_CATEGORY


async def direct_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    if text in all_cancel_texts():
        return await direct_cancel(update, context)

    context.user_data["category"] = text
    await update.message.reply_text(s["direct_step3"], parse_mode="HTML", reply_markup=cancel_kb(lang))
    return DIRECT_DEADLINE


async def direct_deadline_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    if text in all_cancel_texts():
        return await direct_cancel(update, context)

    context.user_data["deadline"] = text.strip()
    await update.message.reply_text(s["direct_step4"], parse_mode="HTML", reply_markup=skip_attachments_kb(lang))
    return DIRECT_ATTACHMENTS


async def direct_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text or ""

    if text in all_cancel_texts():
        return await direct_cancel(update, context)
    if text in all_skip_texts():
        return await _proceed_to_direct_reward(update, context)

    file_id = None
    file_name = ""
    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        if is_blocked_file(file_name):
            await update.message.reply_text(s["direct_file_blocked"].format(name=file_name), parse_mode="HTML")
            return DIRECT_ATTACHMENTS
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
            await update.message.reply_text(s["direct_max_att"])
            return DIRECT_ATTACHMENTS
        atts.append(file_id)
        await update.message.reply_text(s["direct_att_ok"].format(n=len(atts)), reply_markup=skip_attachments_kb(lang))
    else:
        await update.message.reply_text(s["direct_file_unknown"])
    return DIRECT_ATTACHMENTS


async def _proceed_to_direct_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    await update.message.reply_text(s["direct_step5"], parse_mode="HTML", reply_markup=cancel_kb(lang))
    return DIRECT_REWARD


async def direct_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    if text in all_cancel_texts():
        return await direct_cancel(update, context)

    gross = validate_reward(text)
    if gross is None:
        await update.message.reply_text(s["direct_reward_err"], parse_mode="HTML", reply_markup=cancel_kb(lang))
        return DIRECT_REWARD

    user = await get_user(user_id)
    if not user or user["balance_usdt"] < gross:
        bal = user["balance_usdt"] if user else 0.0
        await update.message.reply_text(
            s["direct_insufficient"].format(bal=bal, gross=gross),
            parse_mode="HTML",
            reply_markup=main_menu(lang),
        )
        return ConversationHandler.END

    net = calc_net_reward(gross, PLATFORM_FEE_RATE)
    ud  = context.user_data
    title          = ud["title"]
    category       = ud.get("category", s["cat_general"])
    deadline       = ud.get("deadline", s["na"])
    attachments    = json.dumps(ud.get("attachments", []))
    target_username = ud["direct_target"]

    token    = uuid.uuid4().hex[:TOKEN_LEN]
    identity = f"{target_username}|{token}"

    ok = await freeze_funds(user_id, gross)
    if not ok:
        await update.message.reply_text(s["direct_freeze_err"], reply_markup=main_menu(lang))
        return ConversationHandler.END

    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks "
            "(client_id, title, description, deadline, category, attachments, "
            " reward_gross, reward_net, status, is_direct, target_executor_identity) "
            "VALUES (?,?,?,?,?,?,?,?,'open',1,?)",
            (user_id, title, title, deadline, category, attachments, gross, net, identity),
        )
        task_id = cursor.lastrowid
        await conn.execute(
            "UPDATE users SET total_tasks_client = total_tasks_client + 1 WHERE telegram_id = ?",
            (user_id,),
        )
        await conn.commit()

    bot_user  = await update.get_bot().get_me()
    deep_link = f"https://t.me/{bot_user.username}?start=direct_{token}"
    share_kb  = InlineKeyboardMarkup([[InlineKeyboardButton(s["btn_open_invite"], url=deep_link)]])

    await update.message.reply_text(
        s["direct_created"].format(id=task_id, title=title, username=target_username, gross=gross, link=deep_link),
        parse_mode="HTML",
        reply_markup=share_kb,
    )
    context.user_data.clear()
    return ConversationHandler.END


async def handle_direct_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    token   = context.args[0][len("direct_"):]
    user_id = update.effective_user.id
    lang    = await get_lang(user_id, context)
    s       = STRINGS[lang]

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE is_direct=1 AND status='open' AND target_executor_identity LIKE ?",
            (f"%|{token}",),
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await update.message.reply_text(s["direct_invalid_link"], reply_markup=main_menu(lang))
        return

    task = dict(task)
    if task["client_id"] == user_id:
        await update.message.reply_text(s["direct_own_task"], reply_markup=main_menu(lang))
        return

    await update.message.reply_text(
        s["direct_offer"].format(
            title=task["title"],
            category=task.get("category", s["cat_general"]),
            deadline=task.get("deadline", s["na"]),
            net=task["reward_net"],
        ),
        parse_mode="HTML",
        reply_markup=direct_deal_offer_kb(task["task_id"], token, lang),
    )


async def direct_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang    = await get_lang(user_id, context)
    s       = STRINGS[lang]

    parts   = query.data.split("_")
    task_id = int(parts[2])
    token   = parts[3]

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE task_id=? AND status='open' AND is_direct=1", (task_id,)
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await query.answer(s["direct_unavailable"], show_alert=True)
        return
    task = dict(task)
    if task["client_id"] == user_id:
        await query.answer(s["direct_own_task"], show_alert=True)
        return

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("BEGIN")
        async with conn.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] != "open":
            await conn.execute("ROLLBACK")
            await query.answer(s["direct_taken"], show_alert=True)
            return
        await conn.execute(
            "UPDATE tasks SET status='in_progress', executor_id=?, claimed_at=CURRENT_TIMESTAMP WHERE task_id=?",
            (user_id, task_id),
        )
        await conn.execute("COMMIT")

    room_token = uuid.uuid4().hex
    await create_deal_session(task_id, task["client_id"], user_id, room_token)

    # Notify client in their language
    client_lang = await db_get_user_language(task["client_id"])
    cs = STRINGS[client_lang]
    try:
        await context.bot.send_message(
            chat_id=task["client_id"],
            text=cs["direct_accepted_client"].format(id=task_id, title=task["title"]),
            parse_mode="HTML",
            reply_markup=client_room_kb(task_id, client_lang),
        )
    except Exception as e:
        logger.error("Could not notify direct deal client: %s", e)

    await query.message.reply_text(
        s["direct_accepted_executor"].format(id=task_id, title=task["title"], net=task["reward_net"]),
        parse_mode="HTML",
        reply_markup=executor_room_kb(task_id, lang),
    )


async def direct_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang    = await get_lang(user_id, context)
    s       = STRINGS[lang]

    parts   = query.data.split("_")
    task_id = int(parts[2])

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM tasks WHERE task_id=? AND status='open' AND is_direct=1", (task_id,)
        ) as cursor:
            task = await cursor.fetchone()

    if not task:
        await query.answer(s["direct_already_handled"], show_alert=True)
        return
    task = dict(task)
    await refund_client(task_id)

    client_lang = await db_get_user_language(task["client_id"])
    cs = STRINGS[client_lang]
    try:
        await context.bot.send_message(
            chat_id=task["client_id"],
            text=cs["direct_declined_client"].format(
                id=task_id, title=task["title"], gross=task["reward_gross"]
            ),
            parse_mode="HTML",
            reply_markup=main_menu(client_lang),
        )
    except Exception as e:
        logger.error("Could not notify client of decline: %s", e)

    await query.message.reply_text(
        s["direct_declined_executor"].format(title=task["title"]),
        parse_mode="HTML",
        reply_markup=main_menu(lang),
    )


async def direct_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await get_lang(update.effective_user.id, context)
    s = STRINGS[lang]
    context.user_data.clear()
    await update.message.reply_text(s["direct_cancelled"], reply_markup=main_menu(lang))
    return ConversationHandler.END


async def db_get_user_language(telegram_id: int) -> str:
    import database as db
    lang = await db.get_user_language(telegram_id)
    return lang or DEFAULT_LANG
