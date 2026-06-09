from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["💼 Area Committente", "🛠️ Area Esecutore"],
        ["🤝 Nuovo Affare Diretto", "💰 Portafoglio"],
        ["📂 I Miei Chat", "ℹ️ Supporto"],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

CANCEL_KB = ReplyKeyboardMarkup(
    [["❌ Annulla"]],
    resize_keyboard=True,
    one_time_keyboard=False,
)

CATEGORIES = [
    "📝 Tesi & Ricerca",
    "💻 Informatica",
    "📐 Matematica & Fisica",
    "🔬 Scienze",
    "📚 Letteratura & Lingue",
    "🎨 Grafica & Design",
    "📊 Economia & Business",
    "⚖️ Giurisprudenza",
    "🏥 Medicina & Salute",
    "🌐 Generale",
]

CATEGORY_KB = ReplyKeyboardMarkup(
    [[c] for c in CATEGORIES] + [["❌ Annulla"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def task_channel_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🤝 Prendo l'incarico", callback_data=f"claim_{task_id}")]]
    )


def client_room_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔒 Conferma Completamento", callback_data=f"complete_{task_id}")],
            [InlineKeyboardButton("🚨 Apri Controversia", callback_data=f"dispute_{task_id}")],
        ]
    )


def executor_room_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🚨 Apri Controversia", callback_data=f"dispute_{task_id}")]]
    )


def admin_dispute_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 Sblocca per Esecutore", callback_data=f"adm_exec_{task_id}")],
            [InlineKeyboardButton("🔴 Rimborsa Committente", callback_data=f"adm_client_{task_id}")],
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
            [InlineKeyboardButton("✅ Accetta l'incarico", callback_data=f"direct_accept_{task_id}_{token}")],
            [InlineKeyboardButton("❌ Rifiuta", callback_data=f"direct_decline_{task_id}_{token}")],
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
            [InlineKeyboardButton("💵 Paga da Saldo USDT", callback_data="task_pay_usdt")],
            [InlineKeyboardButton("⭐ Paga con Telegram Stars", callback_data="task_pay_stars")],
        ]
    )


def skip_attachments_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["⏭ Salta allegati"], ["❌ Annulla"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
