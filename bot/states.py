from telegram.ext import ConversationHandler

# Task creation wizard states (committente)
(
    TASK_TITLE,
    TASK_CATEGORY,
    TASK_DEADLINE,
    TASK_ATTACHMENTS,
    TASK_REWARD,
) = range(5)

# Direct deal states
(
    DIRECT_TARGET,
    DIRECT_TITLE,
    DIRECT_CATEGORY,
    DIRECT_DEADLINE,
    DIRECT_ATTACHMENTS,
    DIRECT_REWARD,
) = range(5, 11)

# Top-up states
(
    TOPUP_AMOUNT_CRYPTO,
    TOPUP_AMOUNT_STARS,
) = range(11, 13)

# Withdrawal state
WITHDRAWAL_AMOUNT = 13
