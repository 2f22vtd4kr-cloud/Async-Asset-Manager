from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["💼 Auftraggeber-Bereich", "🛠️ Auftragnehmer-Bereich"],
        ["🤝 Neues Direktgeschäft", "💰 Wallet"],
        ["📂 Meine Chats", "ℹ️ Support"],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

CANCEL_KB = ReplyKeyboardMarkup(
    [["❌ Abbrechen"]],
    resize_keyboard=True,
    one_time_keyboard=False,
)

CATEGORIES = [
    "📝 Abschlussarbeit & Forschung",
    "💻 Informatik",
    "📐 Mathematik & Physik",
    "🔬 Naturwissenschaften",
    "📚 Literatur & Sprachen",
    "🎨 Grafik & Design",
    "📊 Wirtschaft & Business",
    "⚖️ Rechtswissenschaften",
    "🏥 Medizin & Gesundheit",
    "🌐 Allgemein",
]

CATEGORY_KB = ReplyKeyboardMarkup(
    [[c] for c in CATEGORIES] + [["❌ Abbrechen"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def task_channel_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🤝 Auftrag annehmen", callback_data=f"claim_{task_id}")]]
    )


def client_room_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔒 Abschluss bestätigen", callback_data=f"complete_{task_id}")],
            [InlineKeyboardButton("🚨 Streitfall eröffnen", callback_data=f"dispute_{task_id}")],
        ]
    )


def executor_room_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🚨 Streitfall eröffnen", callback_data=f"dispute_{task_id}")]]
    )


def admin_dispute_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 Für Auftragnehmer freigeben", callback_data=f"adm_exec_{task_id}")],
            [InlineKeyboardButton("🔴 Auftraggeber erstatten", callback_data=f"adm_client_{task_id}")],
        ]
    )


def topup_method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 CryptoBot (USDT)", callback_data="topup_crypto")],
            [InlineKeyboardButton("⭐ Telegram Stars", callback_data="topup_stars")],
        ]
    )


def direct_deal_offer_kb(task_id: int, token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Auftrag akzeptieren", callback_data=f"direct_accept_{task_id}_{token}")],
            [InlineKeyboardButton("❌ Ablehnen", callback_data=f"direct_decline_{task_id}_{token}")],
        ]
    )


def rating_kb(task_id: int, target_role: str) -> InlineKeyboardMarkup:
    """target_role: 'exec' (rate executor) or 'client' (rate client)."""
    row = [
        InlineKeyboardButton(f"{'⭐' * n}", callback_data=f"rate_{target_role}_{task_id}_{n}")
        for n in range(1, 6)
    ]
    return InlineKeyboardMarkup([row])


def task_payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💵 Mit USDT-Guthaben zahlen", callback_data="task_pay_usdt")],
            [InlineKeyboardButton("⭐ Mit Telegram Stars zahlen", callback_data="task_pay_stars")],
        ]
    )


def skip_attachments_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["⏭ Anhänge überspringen"], ["❌ Abbrechen"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
