import json
import logging
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import ContextTypes, ConversationHandler
from config import TELEGRAM_CHANNEL_ID, PLATFORM_FEE_RATE, STAR_TO_USDT_RATE
from keyboards import (
    main_menu, cancel_kb, category_kb,
    task_channel_kb, skip_attachments_kb, task_payment_kb,
)
from states import TASK_TITLE, TASK_CATEGORY, TASK_DEADLINE, TASK_ATTACHMENTS, TASK_REWARD
from utils import validate_reward, calc_net_reward, calc_stars_for_usdt, is_blocked_file
from strings import STRINGS, get_lang
import database as db

logger = logging.getLogger(__name__)


async def area_committente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    user = await db.get_user(user_id)
    bal    = user["balance_usdt"] if user else 0.0
    frozen = user["frozen_usdt"] if user else 0.0
    tasks  = await db.get_user_tasks_as_client(user_id)
    open_tasks   = [t for t in tasks if t["status"] == "open"]
    active_tasks = [t for t in tasks if t["status"] == "in_progress"]
    rating  = user["client_rating"] if user else 5.0
    reviews = user["client_reviews_count"] if user else 0

    text = (
        f"{s['client_header']}\n\n"
        f"{s['balance_avail']}: <b>{bal:.2f} USDT</b>\n"
        f"{s['balance_frozen']}: <b>{frozen:.2f} USDT</b>\n"
        f"{s['rating_line']}: <b>{rating:.1f}/5.0</b> ({reviews} {s['reviews_label']})\n\n"
        f"{s['open_tasks_line']}: {len(open_tasks)}\n"
        f"{s['active_tasks_line']}: {len(active_tasks)}\n\n"
        f"{s['publish_hint']}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(s["btn_publish_task"], callback_data="start_task_wizard")],
        [InlineKeyboardButton(s["btn_my_tasks"],     callback_data="my_tasks_client")],
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def start_task_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    if query:
        await query.answer()
        send = query.message.reply_text
    else:
        send = update.message.reply_text

    context.user_data["attachments"] = []

    await send(
        s["wiz_step1"],
        parse_mode="HTML",
        reply_markup=cancel_kb(lang),
    )
    return TASK_TITLE


async def task_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    from strings import all_cancel_texts
    if text in all_cancel_texts():
        return await cancel_wizard(update, context)

    title = text.strip()
    if len(title) < 5 or len(title) > 200:
        await update.message.reply_text(s["wiz_title_err"], reply_markup=cancel_kb(lang))
        return TASK_TITLE

    context.user_data["title"] = title
    await update.message.reply_text(
        s["wiz_step2"], parse_mode="HTML", reply_markup=category_kb(lang)
    )
    return TASK_CATEGORY


async def task_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    from strings import all_cancel_texts
    if text in all_cancel_texts():
        return await cancel_wizard(update, context)

    context.user_data["category"] = text
    await update.message.reply_text(
        s["wiz_deadline"], parse_mode="HTML", reply_markup=cancel_kb(lang)
    )
    return TASK_DEADLINE


async def task_deadline_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    from strings import all_cancel_texts
    if text in all_cancel_texts():
        return await cancel_wizard(update, context)

    context.user_data["deadline"] = text.strip()
    await update.message.reply_text(
        s["wiz_step3"], parse_mode="HTML", reply_markup=skip_attachments_kb(lang)
    )
    return TASK_ATTACHMENTS


async def task_attachment_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text or ""

    from strings import all_cancel_texts, all_skip_texts
    if text in all_cancel_texts():
        return await cancel_wizard(update, context)
    if text in all_skip_texts():
        return await proceed_to_reward(update, context)

    file_id = None
    file_name = ""

    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        if is_blocked_file(file_name):
            await update.message.reply_text(
                s["wiz_file_blocked"].format(name=file_name), parse_mode="HTML"
            )
            return TASK_ATTACHMENTS
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
            await update.message.reply_text(s["wiz_max_att"])
            return TASK_ATTACHMENTS
        atts.append(file_id)
        await update.message.reply_text(
            s["wiz_att_ok"].format(n=len(atts)),
            reply_markup=skip_attachments_kb(lang),
        )
    else:
        await update.message.reply_text(s["wiz_file_unknown"])
    return TASK_ATTACHMENTS


async def proceed_to_reward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    await update.message.reply_text(
        s["wiz_step4"], parse_mode="HTML", reply_markup=cancel_kb(lang)
    )
    return TASK_REWARD


async def task_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]
    text = update.message.text

    from strings import all_cancel_texts
    if text in all_cancel_texts():
        return await cancel_wizard(update, context)

    gross = validate_reward(text)
    if gross is None:
        await update.message.reply_text(
            s["wiz_reward_err"], parse_mode="HTML", reply_markup=cancel_kb(lang)
        )
        return TASK_REWARD

    net = calc_net_reward(gross, PLATFORM_FEE_RATE)
    stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
    ud = context.user_data

    context.user_data["pending_task"] = {
        "title":       ud.get("title", ""),
        "category":    ud.get("category", s["cat_general"]),
        "deadline":    ud.get("deadline", s["na"]),
        "attachments": json.dumps(ud.get("attachments", [])),
        "gross":       gross,
        "net":         net,
    }

    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0

    await update.message.reply_text(
        f"{s['pay_method']}\n\n"
        f"{s['pay_gross']}: <b>{gross:.2f} USDT</b>\n"
        f"{s['pay_net']}: <b>{net:.2f} USDT</b>\n\n"
        f"{s['pay_balance']}: <b>{bal:.2f}</b>\n"
        f"{s['pay_stars_equiv']}: <b>{stars_needed} Stars</b>\n\n"
        f"{s['pay_choose']}",
        parse_mode="HTML",
        reply_markup=task_payment_kb(lang),
    )
    return ConversationHandler.END


async def task_pay_usdt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    pending = context.user_data.get("pending_task")
    if not pending:
        await query.message.reply_text(s["pay_expired"], reply_markup=main_menu(lang))
        return

    gross = pending["gross"]
    user = await db.get_user(user_id)
    bal = user["balance_usdt"] if user else 0.0

    if not user or bal < gross:
        stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
        await query.message.reply_text(
            s["pay_insufficient"].format(bal=bal, gross=gross, stars=stars_needed),
            parse_mode="HTML",
            reply_markup=task_payment_kb(lang),
        )
        return

    ok = await db.freeze_funds(user_id, gross)
    if not ok:
        await query.message.reply_text(s["pay_freeze_err"], reply_markup=main_menu(lang))
        return

    task_id = await _insert_task(user_id, pending)
    context.user_data.pop("pending_task", None)
    await _post_to_channel(update.get_bot(), task_id, pending, lang)

    await query.message.reply_text(
        s["pay_published"].format(id=task_id, title=pending["title"], gross=gross),
        parse_mode="HTML",
        reply_markup=main_menu(lang),
    )


async def task_pay_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    pending = context.user_data.get("pending_task")
    if not pending:
        await query.message.reply_text(s["pay_expired"], reply_markup=main_menu(lang))
        return

    gross = pending["gross"]
    stars_needed = calc_stars_for_usdt(gross, STAR_TO_USDT_RATE)
    title_short = pending["title"][:50]

    await context.bot.send_invoice(
        chat_id=user_id,
        title=f"Escrow: {title_short}",
        description=s["pay_stars_desc"].format(gross=gross),
        payload=f"task_stars_{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label=s["pay_stars_label"], amount=stars_needed)],
        provider_token="",
    )


async def _insert_task(client_id: int, pending: dict) -> int:
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO tasks "
            "(client_id, title, description, deadline, category, attachments, reward_gross, reward_net, status) "
            "VALUES (?,?,?,?,?,?,?,?,'open')",
            (
                client_id,
                pending["title"],
                pending["title"],
                pending["deadline"],
                pending["category"],
                pending["attachments"],
                pending["gross"],
                pending["net"],
            ),
        )
        task_id = cursor.lastrowid
        await conn.commit()
    return task_id


async def _post_to_channel(bot, task_id: int, pending: dict, lang: str = "de") -> None:
    import aiosqlite
    from database import DB_PATH
    from strings import STRINGS
    s = STRINGS.get(lang, STRINGS["de"])
    gross = pending["gross"]
    net   = pending["net"]
    title = pending["title"]
    category = pending.get("category", s["cat_general"])
    deadline = pending.get("deadline", s["na"])

    channel_text = (
        f"📋 <b>{title}</b> {s['channel_tag']}\n\n"
        f"🏷 {category} | 📅 {deadline}\n"
        f"💰 {s['pay_gross']}: <b>{gross:.2f} USDT</b> (net: {net:.2f})\n\n"
        f"{s['summary_id']}: <code>{task_id}</code>"
    )
    try:
        msg = await bot.send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=channel_text,
            parse_mode="HTML",
            reply_markup=task_channel_kb(task_id, lang),
        )
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "UPDATE tasks SET channel_message_id = ? WHERE task_id = ?",
                (msg.message_id, task_id),
            )
            await conn.commit()
    except Exception as e:
        logger.error("Channel publish error: %s", e)


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await get_lang(update.effective_user.id, context)
    s = STRINGS[lang]
    context.user_data.clear()
    await update.message.reply_text(s["wiz_cancelled"], reply_markup=main_menu(lang))
    return ConversationHandler.END


async def my_tasks_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = await get_lang(user_id, context)
    s = STRINGS[lang]

    tasks = await db.get_user_tasks_as_client(user_id)
    if not tasks:
        await query.message.reply_text(s["no_tasks_client"])
        return
    from utils import format_task_summary
    for t in tasks[:10]:
        await query.message.reply_text(format_task_summary(t, lang), parse_mode="HTML")
