from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from strings import STRINGS, DEFAULT_LANG


def _s(lang: str) -> dict:
    return STRINGS.get(lang, STRINGS[DEFAULT_LANG])


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    s = _s(lang)
    return ReplyKeyboardMarkup(
        [
            [s["btn_client"],   s["btn_executor"]],
            [s["btn_direct"],   s["btn_wallet"]],
            [s["btn_chats"],    s["btn_support"]],
            [s["btn_language"]],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def cancel_kb(lang: str) -> ReplyKeyboardMarkup:
    s = _s(lang)
    return ReplyKeyboardMarkup(
        [[s["btn_cancel"]]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def category_kb(lang: str) -> ReplyKeyboardMarkup:
    s = _s(lang)
    cats = s["categories"]
    return ReplyKeyboardMarkup(
        [[c] for c in cats] + [[s["btn_cancel"]]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_attachments_kb(lang: str) -> ReplyKeyboardMarkup:
    s = _s(lang)
    return ReplyKeyboardMarkup(
        [[s["btn_skip_attachments"]], [s["btn_cancel"]]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def language_select_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"),
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_lang_de"),
        ]
    ])


def task_channel_kb(task_id: int, lang: str) -> InlineKeyboardMarkup:
    s = _s(lang)
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(s["btn_claim_task"], callback_data=f"claim_{task_id}")]]
    )


def client_room_kb(task_id: int, lang: str) -> InlineKeyboardMarkup:
    s = _s(lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(s["btn_confirm_complete"], callback_data=f"complete_{task_id}")],
        [InlineKeyboardButton(s["btn_open_dispute"],     callback_data=f"dispute_{task_id}")],
    ])


def executor_room_kb(task_id: int, lang: str) -> InlineKeyboardMarkup:
    s = _s(lang)
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(s["btn_open_dispute"], callback_data=f"dispute_{task_id}")]]
    )


def admin_dispute_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Release to Executor", callback_data=f"adm_exec_{task_id}")],
        [InlineKeyboardButton("🔴 Refund Client",       callback_data=f"adm_client_{task_id}")],
    ])


def topup_method_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 CryptoBot (USDT)", callback_data="topup_crypto")],
        [InlineKeyboardButton("⭐ Telegram Stars",   callback_data="topup_stars")],
    ])


def direct_deal_offer_kb(task_id: int, token: str, lang: str) -> InlineKeyboardMarkup:
    s = _s(lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(s["btn_accept_task"],  callback_data=f"direct_accept_{task_id}_{token}")],
        [InlineKeyboardButton(s["btn_decline_task"], callback_data=f"direct_decline_{task_id}_{token}")],
    ])


def rating_kb(task_id: int, target_role: str) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(f"{'⭐' * n}", callback_data=f"rate_{target_role}_{task_id}_{n}")
        for n in range(1, 6)
    ]
    return InlineKeyboardMarkup([row])


def task_payment_kb(lang: str) -> InlineKeyboardMarkup:
    s = _s(lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(s["btn_pay_usdt"],  callback_data="task_pay_usdt")],
        [InlineKeyboardButton(s["btn_pay_stars"], callback_data="task_pay_stars")],
    ])
