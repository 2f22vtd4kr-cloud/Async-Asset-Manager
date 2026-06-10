"""
Master translation file.
Usage:
    from strings import STRINGS, get_lang
    s = STRINGS[lang]
    await msg.reply_text(s["welcome"])
"""
from __future__ import annotations

DEFAULT_LANG = "de"

STRINGS: dict[str, dict] = {
    # ──────────────────────────────────────────────────────
    "en": {
        # Menu buttons (reply keyboard)
        "btn_client":            "💼 Client Area",
        "btn_executor":          "🛠️ Executor Area",
        "btn_direct":            "🤝 New Direct Deal",
        "btn_wallet":            "💰 Wallet",
        "btn_chats":             "📂 My Chats",
        "btn_support":           "ℹ️ Support",
        "btn_language":          "🌐 Language",
        "btn_cancel":            "❌ Cancel",
        "btn_skip_attachments":  "⏭ Skip attachments",

        # Inline buttons
        "btn_publish_task":      "📝 Publish Task",
        "btn_my_tasks":          "📋 My Tasks",
        "btn_channel":           "📢 Go to Task Channel",
        "btn_claim_task":        "🤝 Take this task",
        "btn_confirm_complete":  "🔒 Confirm Completion",
        "btn_open_dispute":      "🚨 Open Dispute",
        "btn_admin_release":     "🟢 Release to Executor",
        "btn_admin_refund":      "🔴 Refund Client",
        "btn_pay_usdt":          "💵 Pay from USDT Balance",
        "btn_pay_stars":         "⭐ Pay with Telegram Stars",
        "btn_accept_task":       "✅ Accept task",
        "btn_decline_task":      "❌ Decline",
        "btn_open_invite":       "🔗 Open invite link",

        # Language selection
        "lang_choose":  "🌐 <b>Please choose your language:</b>",
        "lang_set_en":  "✅ Language set to <b>English</b>.",
        "lang_set_de":  "✅ Language set to <b>Deutsch</b>.",

        # Welcome & common
        "welcome": (
            "🐸 <b>Welcome to Fai un Salto!</b>\n\n"
            "The P2P platform for students.\n"
            "Post tasks, find collaborators and handle payments securely.\n\n"
            "Choose an option from the menu below:"
        ),
        "support": (
            "ℹ️ <b>Fai un Salto Support</b>\n\n"
            "For help, contact our team:\n"
            "• Dispute? Use the 🚨 button in the deal chat.\n"
            "• Technical issues? Write to @FaiUnSaltoSupport\n"
            "• Fees: 10% on every completed task.\n"
            "• Stars → USDT rate: 1 Star = 0.02 USDT"
        ),
        "my_chats_empty":  "📂 <b>My Active Chats</b>\n\nNo active chats at the moment.",
        "my_chats_header": "📂 <b>My Active Chats</b> ({n} deals)",
        "my_chats_hint":   "Write in any active chat: your message will be forwarded anonymously.",
        "role_client":     "Client",
        "role_executor":   "Executor",
        "unknown_cmd":     "❓ Unknown command. Use the menu below.",
        "account_blocked": "🚫 Your account has been suspended.",
        "na":              "N/A",

        # Status labels
        "status_open":        "🟢 Open",
        "status_in_progress": "🟡 In Progress",
        "status_completed":   "✅ Completed",
        "status_dispute":     "🔴 Dispute",
        "status_cancelled":   "❌ Cancelled",

        # Categories
        "categories": [
            "📝 Thesis & Research",
            "💻 Computer Science",
            "📐 Math & Physics",
            "🔬 Sciences",
            "📚 Literature & Languages",
            "🎨 Graphics & Design",
            "📊 Economics & Business",
            "⚖️ Law",
            "🏥 Medicine & Health",
            "🌐 General",
        ],
        "cat_general": "General",

        # Task summary
        "summary_category": "🏷 Category",
        "summary_deadline":  "📅 Deadline",
        "summary_gross":     "💰 Gross reward",
        "summary_net":       "💵 Net (executor)",
        "summary_status":    "🔖 Status",
        "summary_id":        "🆔 Task ID",

        # Client area
        "client_header":    "💼 <b>Client Area</b>",
        "balance_avail":    "💰 Available balance",
        "balance_frozen":   "🔒 In escrow",
        "rating_line":      "⭐ Rating",
        "reviews_label":    "reviews",
        "open_tasks_line":  "📋 Open tasks",
        "active_tasks_line":"⚙️ Active tasks",
        "publish_hint":     "Use <b>Publish Task</b> to create a new job.",
        "no_tasks_client":  "📋 No tasks published yet.",

        # Wizard
        "wiz_step1":        "📝 <b>Step 1/4 — Task title</b>\n\nWrite a clear and concise title for your task:",
        "wiz_title_err":    "⚠️ Title must be between 5 and 200 characters. Try again:",
        "wiz_step2":        "🏷 <b>Step 2/4 — Category & Deadline</b>\n\nChoose the category:",
        "wiz_deadline":     "📅 Enter the <b>deadline</b>\n(e.g. <i>July 15 2025</i> or <i>within 3 days</i>):",
        "wiz_step3": (
            "📎 <b>Step 3/4 — Attachments</b>\n\n"
            "Send files, images or documents (up to 50 MB each).\n"
            "When done press <b>⏭ Skip attachments</b>."
        ),
        "wiz_file_blocked": "🚫 File <code>{name}</code> not allowed for security reasons.",
        "wiz_max_att":      "⚠️ Maximum 10 attachments. Press ⏭ to continue.",
        "wiz_att_ok":       "✅ Attachment {n}/10 received. Send more or press ⏭.",
        "wiz_file_unknown": "⚠️ Unknown file type. Send a document, photo, video or audio.",
        "wiz_step4": (
            "💰 <b>Step 4/4 — Gross Reward</b>\n\n"
            "Enter the reward in <b>USDT</b> you want to offer.\n"
            "⚠️ 90% goes to the executor upon completion (10% platform fee).\n\n"
            "You can pay the escrow with your USDT balance <b>or</b> with <b>Telegram Stars</b>."
        ),
        "wiz_reward_err":   "⚠️ Invalid amount. Enter a positive number (e.g. <code>15.00</code>):",
        "wiz_cancelled":    "❌ Operation cancelled.",

        # Payment method
        "pay_method":       "💳 <b>Escrow payment method</b>",
        "pay_gross":        "Gross reward",
        "pay_net":          "Net (executor)",
        "pay_balance":      "💵 Your USDT balance",
        "pay_stars_equiv":  "⭐ Stars equivalent",
        "pay_choose":       "Choose how you want to pay:",
        "pay_expired":      "❌ Session expired. Please recreate the task.",
        "pay_insufficient": (
            "❌ Insufficient balance. You have <b>{bal:.2f} USDT</b>, "
            "but the task requires <b>{gross:.2f} USDT</b>.\n\n"
            "You can top up via 💰 Wallet or pay with <b>{stars} Telegram Stars</b>:"
        ),
        "pay_freeze_err":   "❌ Error freezing funds. Please try again.",
        "pay_published": (
            "✅ <b>Task published!</b>\n\n"
            "🆔 Task #{id} — {title}\n"
            "💰 Funds locked in escrow: <b>{gross:.2f} USDT</b>"
        ),
        "pay_stars_desc":   "Post task on Fai un Salto\nEscrow amount: {gross:.2f} USDT",
        "pay_stars_label":  "Stars for escrow",

        # Channel
        "channel_tag":         "#Task",
        "channel_in_progress": "🔴 <b>In Progress</b> — Task assigned",

        # Executor area
        "exec_header":       "🛠️ <b>Executor Area</b>",
        "exec_active":       "⚙️ Active tasks",
        "exec_completed":    "✅ Completed",
        "exec_hint":         "Visit the channel to find new available tasks.",
        "exec_no_tasks":     "📋 No tasks taken yet.",
        "exec_not_found":    "❌ Task not found.",
        "exec_unavailable":  "🔴 This task is no longer available.",
        "exec_own_task":     "⚠️ You cannot take your own task.",
        "exec_shadow_ban":   "🚫 Operation not available.",
        "exec_taken":        "🔴 Task already taken.",
        "exec_client_msg": (
            "🤝 <b>Task accepted!</b>\n\n"
            "Task #{id} — {title}\n"
            "An executor accepted your task. The chat is now active.\n"
            "Write here to communicate anonymously."
        ),
        "exec_executor_msg": (
            "✅ <b>Task taken!</b>\n\n"
            "Task #{id} — {title}\n"
            "💰 Net reward: <b>{net:.2f} USDT</b>\n"
            "Write here to communicate with the client anonymously."
        ),

        # Bridge
        "bridge_from_client":  "📩 Message from Client:",
        "bridge_from_executor":"📩 Message from Executor:",
        "bridge_file_blocked": "🚫 File <code>{name}</code> blocked for security reasons.",
        "bridge_doc":          "[Document: {name}]",
        "bridge_photo":        "[Photo]",
        "bridge_video":        "[Video]",
        "bridge_audio":        "[Audio]",
        "bridge_voice":        "[Voice message]",
        "bridge_sticker":      "[Sticker]",
        "bridge_unsupported":  "⚠️ Message type not supported.",
        "bridge_panel":        "🎛 <b>Control Panel</b>",
        "bridge_fwd_fail":     "⚠️ Error forwarding message. Please try again.",
        "bridge_not_allowed":  "❌ Operation not allowed.",
        "bridge_not_active":   "⚠️ This deal is not active.",
        "bridge_release_err":  "❌ Error releasing funds. Please contact support.",
        "bridge_confirmed": (
            "✅ <b>Completion confirmed!</b>\n\n"
            "Task #{id} — {title}\n"
            "The reward has been released to the executor."
        ),
        "bridge_completed": (
            "🎉 <b>Task completed!</b>\n\n"
            "Task #{id} — {title}\n"
            "💰 <b>{net:.2f} USDT</b> credited to your balance."
        ),

        # Admin
        "admin_dispute_hdr":    "🚨 <b>DISPUTE OPENED</b>",
        "admin_client_label":   "👤 Client",
        "admin_executor_label": "🛠 Executor",
        "admin_escrow_label":   "💰 Escrow amount",
        "admin_last_msgs":      "<b>Last messages:</b>",
        "admin_dispute_notify": (
            "🚨 <b>Dispute opened for Task #{id}</b>\n\n"
            "Our team will review the case and communicate the decision.\n"
            "The chat has been paused."
        ),
        "admin_not_auth":          "🚫 Not authorized.",
        "admin_not_found":         "❌ Task not found.",
        "admin_session_not_found": "❌ Session not found.",
        "admin_already_open":      "⚠️ The dispute has already been opened.",
        "admin_release_err":       "❌ Error releasing funds.",
        "admin_refund_err":        "❌ Error processing refund.",
        "admin_release_client":    "⚖️ Dispute Task #{id}: funds have been assigned to the executor.",
        "admin_release_executor":  "🟢 Dispute Task #{id}: you received the reward of {net:.2f} USDT.",
        "admin_release_resolved":  "✅ <b>Resolved: funds released to executor.</b>",
        "admin_refund_client":     "🔴 Dispute Task #{id}: refund completed. {gross:.2f} USDT returned to your balance.",
        "admin_refund_executor":   "⚖️ Dispute Task #{id}: funds have been returned to the client.",
        "admin_refund_resolved":   "🔴 <b>Resolved: client refunded.</b>",
        "admin_stats_hdr":         "📊 <b>Admin Statistics</b>",
        "admin_stats_users":       "👥 Registered users",
        "admin_stats_tasks":       "📋 Tasks by status",
        "admin_stats_fees":        "💰 Total fees",
        "admin_role_client":       "C",
        "admin_role_executor":     "E",

        # Direct deal
        "direct_start": (
            "🤝 <b>New Direct Deal</b>\n\n"
            "Enter the <b>Telegram username</b> of the executor you want to work with.\n"
            "E.g.: <code>@john_doe</code>"
        ),
        "direct_username_err":  "⚠️ Invalid username. Enter a valid Telegram username (e.g. <code>@john_doe</code>):",
        "direct_exec_selected": "👤 Selected executor: <b>{username}</b>",
        "direct_step1":         "📝 <b>Step 1/5 — Task title</b>\n\nWrite a clear and concise title:",
        "direct_title_err":     "⚠️ Title must be between 5 and 200 characters. Try again:",
        "direct_step2":         "🏷 <b>Step 2/5 — Category</b>\n\nChoose the task category:",
        "direct_step3":         "📅 <b>Step 3/5 — Deadline</b>\n\nEnter the deadline (e.g. <i>July 20 2025</i> or <i>within 5 days</i>):",
        "direct_step4": (
            "📎 <b>Step 4/5 — Attachments</b>\n\n"
            "Send files, images or documents (up to 50 MB each).\n"
            "When done press <b>⏭ Skip attachments</b>."
        ),
        "direct_file_blocked":  "🚫 File <code>{name}</code> not allowed.",
        "direct_max_att":       "⚠️ Maximum 10 attachments. Press ⏭ to continue.",
        "direct_att_ok":        "✅ Attachment {n}/10 received. Send more or press ⏭.",
        "direct_file_unknown":  "⚠️ Unknown file type.",
        "direct_step5": (
            "💰 <b>Step 5/5 — Gross Reward</b>\n\n"
            "Enter the reward in <b>USDT</b> you want to offer.\n"
            "⚠️ 10% is retained as platform fee.\n"
            "90% goes to the executor upon completion."
        ),
        "direct_reward_err":    "⚠️ Invalid amount. Enter a positive number (e.g. <code>20.00</code>):",
        "direct_insufficient": (
            "❌ Insufficient balance. You have <b>{bal:.2f} USDT</b>, "
            "but the task requires <b>{gross:.2f} USDT</b>.\n"
            "Top up your wallet via 💰 Wallet."
        ),
        "direct_freeze_err":    "❌ Error freezing funds. Please try again.",
        "direct_created": (
            "✅ <b>Direct deal created!</b>\n\n"
            "🆔 Task #{id} — {title}\n"
            "👤 For: <b>{username}</b>\n"
            "💰 Escrow locked: <b>{gross:.2f} USDT</b>\n\n"
            "📩 Send this link to {username} to let them accept the task:\n"
            "<code>{link}</code>"
        ),
        "direct_invalid_link":  "❌ Invalid link or task no longer available.",
        "direct_own_task":      "⚠️ You cannot accept your own task.",
        "direct_offer": (
            "🤝 <b>Direct Deal Offer</b>\n\n"
            "📋 <b>{title}</b>\n"
            "🏷 {category} | 📅 {deadline}\n"
            "💰 Net reward for you: <b>{net:.2f} USDT</b>\n\n"
            "Do you accept this task?"
        ),
        "direct_unavailable":   "❌ Task no longer available.",
        "direct_taken":         "❌ Task already assigned.",
        "direct_accepted_client": (
            "🎉 <b>Direct Deal accepted!</b>\n\n"
            "Task #{id} — {title}\n"
            "The executor accepted your proposal. The chat is now active.\n"
            "Write here to communicate anonymously."
        ),
        "direct_accepted_executor": (
            "✅ <b>Task accepted!</b>\n\n"
            "Task #{id} — {title}\n"
            "💰 Net reward: <b>{net:.2f} USDT</b>\n\n"
            "Write here to communicate with the client anonymously."
        ),
        "direct_already_handled": "❌ Task already handled.",
        "direct_declined_client": (
            "❌ <b>Direct Deal declined</b>\n\n"
            "Task #{id} — {title}\n"
            "The executor declined the proposal.\n"
            "💰 <b>{gross:.2f} USDT</b> returned to your balance."
        ),
        "direct_declined_executor": "You declined task <b>{title}</b>.\nYou can explore other tasks in the channel.",
        "direct_cancelled":     "❌ Operation cancelled.",

        # Payments
        "wallet_hdr":           "💰 <b>Wallet</b>",
        "wallet_avail":         "💵 Available balance",
        "wallet_frozen":        "🔒 In escrow",
        "wallet_action":        "Top up or withdraw:",
        "topup_crypto_prompt": (
            "💳 <b>Top up via CryptoBot (USDT)</b>\n\n"
            "Enter the USDT amount you want to add (e.g. <code>10.00</code>):"
        ),
        "topup_amount_err":     "⚠️ Invalid amount. Enter a positive number (e.g. <code>10.00</code>):",
        "topup_crypto_desc":    "Top up Fai un Salto — {amount} USDT",
        "topup_pay_btn":        "💳 Pay via CryptoBot P2P",
        "topup_invoice_ok": (
            "✅ Invoice created for <b>{amount:.2f} USDT</b>\n\n"
            "Click the button to complete payment.\n"
            "Balance will update automatically after confirmation."
        ),
        "topup_cryptobot_err":  "❌ Error creating CryptoBot invoice. Please try again later.",
        "topup_conn_err":       "⚠️ CryptoBot connection error. Please try again.",
        "topup_stars_prompt": (
            "⭐ <b>Top up balance via Telegram Stars</b>\n\n"
            "Rate: 1 Star = {rate} USDT\n"
            "⚠️ 10% platform fee applies to top-up.\n\n"
            "Enter the USDT amount you want to add (e.g. <code>5.00</code>):"
        ),
        "topup_stars_title":    "Top up Wallet Balance",
        "topup_stars_desc":     "Top up {amount:.2f} USDT on Fai un Salto (10% fee included)",
        "topup_stars_label":    "Stars",
        "stars_task_missing":   "⚠️ Task data not found. Your Stars are safe — please contact support.",
        "stars_task_ok": (
            "⭐ <b>Stars payment confirmed!</b>\n\n"
            "🆔 Task #{id} — {title}\n"
            "⭐ Stars paid: <b>{stars}</b>\n"
            "💰 Escrow locked: <b>{gross:.2f} USDT</b>\n\n"
            "The task is now visible in the channel."
        ),
        "stars_topup_ok": (
            "⭐ <b>Top-up complete!</b>\n\n"
            "Stars paid: <b>{stars}</b>\n"
            "Gross value: {gross:.4f} USDT\n"
            "Fee (10%): -{fee:.4f} USDT\n"
            "💵 <b>Credited: {net:.4f} USDT</b>"
        ),
        "withdrawal_hdr":       "💸 <b>Withdrawal</b>\n\nUsage: <code>/prelievo &lt;amount&gt;</code>\nE.g: <code>/prelievo 10.00</code>",
        "withdrawal_inv":       "⚠️ Invalid amount. Use: <code>/prelievo 10.00</code>",
        "withdrawal_insuf":     "❌ Insufficient balance. Available: <b>{bal:.2f} USDT</b>, requested: <b>{amount:.2f} USDT</b>.",
        "withdrawal_tx_err":    "❌ Transaction error. Please try again.",
        "withdrawal_comment":   "Withdrawal Fai un Salto",
        "withdrawal_ok":        "✅ <b>Withdrawal confirmed!</b>\n\n💸 <b>{amount:.2f} USDT</b> transferred to your CryptoBot wallet.",
        "withdrawal_net_err":   "⚠️ CryptoBot network error. The amount has been returned to your internal balance.",

        # Rating
        "rating_labels": {1: "😞 Very bad", 2: "😐 Bad", 3: "🙂 OK", 4: "😊 Good", 5: "🌟 Excellent"},
        "rate_exec_prompt":     "⭐ <b>How did the deal go?</b>\nRate the executor:",
        "rate_client_prompt":   "⭐ <b>How did the deal go?</b>\nRate the client:",
        "rated_exec":           "⭐ You rated the executor <b>{stars}</b> — {label}\nThanks for your feedback!",
        "rated_client":         "⭐ You rated the client <b>{stars}</b> — {label}\nThanks for your feedback!",
        "rating_not_found":     "❌ Task not found.",
        "rating_only_client":   "❌ Only the client can rate the executor.",
        "rating_only_executor": "❌ Only the executor can rate the client.",
        "rating_no_executor":   "❌ No executor to rate.",

        # CryptoBot poller
        "cryptobot_topup_ok":   "✅ <b>Top-up received!</b>\n\n💵 <b>{amount:.4f} USDT</b> credited to your balance.",
    },

    # ──────────────────────────────────────────────────────
    "de": {
        # Menu buttons
        "btn_client":            "💼 Auftraggeber-Bereich",
        "btn_executor":          "🛠️ Auftragnehmer-Bereich",
        "btn_direct":            "🤝 Neues Direktgeschäft",
        "btn_wallet":            "💰 Wallet",
        "btn_chats":             "📂 Meine Chats",
        "btn_support":           "ℹ️ Support",
        "btn_language":          "🌐 Sprache",
        "btn_cancel":            "❌ Abbrechen",
        "btn_skip_attachments":  "⏭ Anhänge überspringen",

        # Inline buttons
        "btn_publish_task":      "📝 Auftrag veröffentlichen",
        "btn_my_tasks":          "📋 Meine Aufträge",
        "btn_channel":           "📢 Zum Auftragskanal",
        "btn_claim_task":        "🤝 Auftrag annehmen",
        "btn_confirm_complete":  "🔒 Abschluss bestätigen",
        "btn_open_dispute":      "🚨 Streitfall eröffnen",
        "btn_admin_release":     "🟢 Für Auftragnehmer freigeben",
        "btn_admin_refund":      "🔴 Auftraggeber erstatten",
        "btn_pay_usdt":          "💵 Mit USDT-Guthaben zahlen",
        "btn_pay_stars":         "⭐ Mit Telegram Stars zahlen",
        "btn_accept_task":       "✅ Auftrag akzeptieren",
        "btn_decline_task":      "❌ Ablehnen",
        "btn_open_invite":       "🔗 Einladungslink öffnen",

        # Language selection
        "lang_choose":  "🌐 <b>Bitte wähle deine Sprache:</b>",
        "lang_set_en":  "✅ Sprache auf <b>English</b> gesetzt.",
        "lang_set_de":  "✅ Sprache auf <b>Deutsch</b> gesetzt.",

        # Welcome & common
        "welcome": (
            "🐸 <b>Willkommen bei Fai un Salto!</b>\n\n"
            "Die P2P-Plattform für Studierende.\n"
            "Veröffentliche Aufträge, finde Mitarbeiter und wickle Zahlungen sicher ab.\n\n"
            "Wähle eine Option aus dem Menü unten:"
        ),
        "support": (
            "ℹ️ <b>Support – Fai un Salto</b>\n\n"
            "Für Hilfe kontaktiere unser Team:\n"
            "• Streitfall? Nutze den 🚨-Button im Deal-Chat.\n"
            "• Technische Probleme? Schreibe an @FaiUnSaltoSupport\n"
            "• Gebühren: 10% auf jeden abgeschlossenen Auftrag.\n"
            "• Umrechnung Stars → USDT: 1 Star = 0,02 USDT"
        ),
        "my_chats_empty":  "📂 <b>Meine aktiven Chats</b>\n\nDerzeit keine aktiven Chats.",
        "my_chats_header": "📂 <b>Meine aktiven Chats</b> ({n} Deals)",
        "my_chats_hint":   "Schreibe in einen aktiven Chat: die Nachricht wird automatisch anonym weitergeleitet.",
        "role_client":     "Auftraggeber",
        "role_executor":   "Auftragnehmer",
        "unknown_cmd":     "❓ Unbekannter Befehl. Nutze das Menü unten.",
        "account_blocked": "🚫 Dein Konto wurde gesperrt.",
        "na":              "k.A.",

        # Status labels
        "status_open":        "🟢 Offen",
        "status_in_progress": "🟡 In Bearbeitung",
        "status_completed":   "✅ Abgeschlossen",
        "status_dispute":     "🔴 Streitfall",
        "status_cancelled":   "❌ Storniert",

        # Categories
        "categories": [
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
        ],
        "cat_general": "Allgemein",

        # Task summary
        "summary_category": "🏷 Kategorie",
        "summary_deadline":  "📅 Frist",
        "summary_gross":     "💰 Bruttovergütung",
        "summary_net":       "💵 Netto Auftragnehmer",
        "summary_status":    "🔖 Status",
        "summary_id":        "🆔 Auftrags-ID",

        # Client area
        "client_header":     "💼 <b>Auftraggeber-Bereich</b>",
        "balance_avail":     "💰 Verfügbares Guthaben",
        "balance_frozen":    "🔒 Im Treuhand",
        "rating_line":       "⭐ Bewertung",
        "reviews_label":     "Bewertungen",
        "open_tasks_line":   "📋 Offene Aufträge",
        "active_tasks_line": "⚙️ Laufende Aufträge",
        "publish_hint":      "Nutze <b>Auftrag veröffentlichen</b>, um einen neuen Job zu erstellen.",
        "no_tasks_client":   "📋 Noch keine Aufträge veröffentlicht.",

        # Wizard
        "wiz_step1":        "📝 <b>Schritt 1/4 — Aufragstitel</b>\n\nSchreibe einen klaren und prägnanten Titel für deinen Auftrag:",
        "wiz_title_err":    "⚠️ Der Titel muss zwischen 5 und 200 Zeichen lang sein. Nochmal versuchen:",
        "wiz_step2":        "🏷 <b>Schritt 2/4 — Kategorie & Frist</b>\n\nWähle die Kategorie:",
        "wiz_deadline":     "📅 Gib die <b>Frist</b> des Auftrags ein\n(z.B. <i>15. Juli 2025</i> oder <i>innerhalb von 3 Tagen</i>):",
        "wiz_step3": (
            "📎 <b>Schritt 3/4 — Anhänge</b>\n\n"
            "Sende Dateien, Bilder oder Dokumente (bis zu 50 MB pro Datei).\n"
            "Wenn du fertig bist, drücke <b>⏭ Anhänge überspringen</b>."
        ),
        "wiz_file_blocked": "🚫 Datei <code>{name}</code> aus Sicherheitsgründen nicht erlaubt.",
        "wiz_max_att":      "⚠️ Maximal 10 Anhänge. Drücke ⏭ zum Fortfahren.",
        "wiz_att_ok":       "✅ Anhang {n}/10 empfangen. Weitere senden oder ⏭ drücken.",
        "wiz_file_unknown": "⚠️ Unbekannter Dateityp. Sende ein Dokument, Foto, Video oder Audio.",
        "wiz_step4": (
            "💰 <b>Schritt 4/4 — Bruttovergütung</b>\n\n"
            "Gib die Vergütung in <b>USDT</b> ein, die du anbieten möchtest.\n"
            "⚠️ 90% gehen bei Abschluss an den Auftragnehmer (10% Plattformgebühr).\n\n"
            "Du kannst den Treuhandbetrag mit deinem USDT-Guthaben <b>oder</b> mit <b>Telegram Stars</b> bezahlen."
        ),
        "wiz_reward_err":   "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>15.00</code>):",
        "wiz_cancelled":    "❌ Vorgang abgebrochen.",

        # Payment method
        "pay_method":       "💳 <b>Treuhand-Zahlungsmethode</b>",
        "pay_gross":        "Bruttovergütung",
        "pay_net":          "Netto Auftragnehmer",
        "pay_balance":      "💵 Dein USDT-Guthaben",
        "pay_stars_equiv":  "⭐ Stars-Äquivalent",
        "pay_choose":       "Wähle die Zahlungsmethode:",
        "pay_expired":      "❌ Sitzung abgelaufen. Bitte Auftrag neu erstellen.",
        "pay_insufficient": (
            "❌ Unzureichendes Guthaben. Du hast <b>{bal:.2f} USDT</b>, "
            "der Auftrag erfordert jedoch <b>{gross:.2f} USDT</b>.\n\n"
            "Du kannst über 💰 Wallet aufladen oder mit "
            "<b>{stars} Telegram Stars</b> zahlen:"
        ),
        "pay_freeze_err":   "❌ Fehler beim Einfrieren der Mittel. Bitte erneut versuchen.",
        "pay_published": (
            "✅ <b>Auftrag veröffentlicht!</b>\n\n"
            "🆔 Auftrag #{id} — {title}\n"
            "💰 Im Treuhand eingefroren: <b>{gross:.2f} USDT</b>"
        ),
        "pay_stars_desc":   "Auftrag auf Fai un Salto veröffentlichen\nTreuhandbetrag: {gross:.2f} USDT",
        "pay_stars_label":  "Stars für Treuhand",

        # Channel
        "channel_tag":         "#Auftrag",
        "channel_in_progress": "🔴 <b>In Bearbeitung</b> — Auftrag vergeben",

        # Executor area
        "exec_header":       "🛠️ <b>Auftragnehmer-Bereich</b>",
        "exec_active":       "⚙️ Aktive Aufträge",
        "exec_completed":    "✅ Abgeschlossen",
        "exec_hint":         "Besuche den Kanal, um neue verfügbare Aufträge zu finden.",
        "exec_no_tasks":     "📋 Noch keine Aufträge übernommen.",
        "exec_not_found":    "❌ Auftrag nicht gefunden.",
        "exec_unavailable":  "🔴 Dieser Auftrag ist nicht mehr verfügbar.",
        "exec_own_task":     "⚠️ Du kannst deinen eigenen Auftrag nicht annehmen.",
        "exec_shadow_ban":   "🚫 Vorgang nicht verfügbar.",
        "exec_taken":        "🔴 Auftrag bereits vergeben.",
        "exec_client_msg": (
            "🤝 <b>Auftrag angenommen!</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "Ein Auftragnehmer hat deinen Auftrag angenommen. Der Chat ist jetzt aktiv.\n"
            "Schreibe hier, um anonym zu kommunizieren."
        ),
        "exec_executor_msg": (
            "✅ <b>Auftrag übernommen!</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "💰 Nettovergütung: <b>{net:.2f} USDT</b>\n"
            "Schreibe hier, um anonym mit dem Auftraggeber zu kommunizieren."
        ),

        # Bridge
        "bridge_from_client":  "📩 Nachricht vom Auftraggeber:",
        "bridge_from_executor":"📩 Nachricht vom Auftragnehmer:",
        "bridge_file_blocked": "🚫 Datei <code>{name}</code> aus Sicherheitsgründen gesperrt.",
        "bridge_doc":          "[Dokument: {name}]",
        "bridge_photo":        "[Foto]",
        "bridge_video":        "[Video]",
        "bridge_audio":        "[Audio]",
        "bridge_voice":        "[Sprachnachricht]",
        "bridge_sticker":      "[Sticker]",
        "bridge_unsupported":  "⚠️ Nachrichtentyp nicht unterstützt.",
        "bridge_panel":        "🎛 <b>Steuerfeld</b>",
        "bridge_fwd_fail":     "⚠️ Fehler beim Weiterleiten der Nachricht. Bitte erneut versuchen.",
        "bridge_not_allowed":  "❌ Vorgang nicht erlaubt.",
        "bridge_not_active":   "⚠️ Dieser Deal ist nicht aktiv.",
        "bridge_release_err":  "❌ Fehler bei der Freigabe der Mittel. Bitte Support kontaktieren.",
        "bridge_confirmed": (
            "✅ <b>Abschluss bestätigt!</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "Die Vergütung wurde an den Auftragnehmer freigegeben."
        ),
        "bridge_completed": (
            "🎉 <b>Auftrag abgeschlossen!</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "💰 <b>{net:.2f} USDT</b> wurden deinem Guthaben gutgeschrieben."
        ),

        # Admin
        "admin_dispute_hdr":    "🚨 <b>STREITFALL ERÖFFNET</b>",
        "admin_client_label":   "👤 Auftraggeber",
        "admin_executor_label": "🛠 Auftragnehmer",
        "admin_escrow_label":   "💰 Treuhandbetrag",
        "admin_last_msgs":      "<b>Letzte Nachrichten:</b>",
        "admin_dispute_notify": (
            "🚨 <b>Streitfall für Auftrag #{id} eröffnet</b>\n\n"
            "Unser Team wird den Fall prüfen und die Entscheidung mitteilen.\n"
            "Der Chat wurde pausiert."
        ),
        "admin_not_auth":          "🚫 Nicht autorisiert.",
        "admin_not_found":         "❌ Auftrag nicht gefunden.",
        "admin_session_not_found": "❌ Sitzung nicht gefunden.",
        "admin_already_open":      "⚠️ Der Streitfall wurde bereits eröffnet.",
        "admin_release_err":       "❌ Fehler bei der Freigabe der Mittel.",
        "admin_refund_err":        "❌ Fehler bei der Rückerstattung.",
        "admin_release_client":    "⚖️ Streitfall Auftrag #{id}: Die Mittel wurden dem Auftragnehmer zugesprochen.",
        "admin_release_executor":  "🟢 Streitfall Auftrag #{id}: Du hast die Vergütung von {net:.2f} USDT erhalten.",
        "admin_release_resolved":  "✅ <b>Gelöst: Mittel an Auftragnehmer freigegeben.</b>",
        "admin_refund_client":     "🔴 Streitfall Auftrag #{id}: Rückerstattung abgeschlossen. {gross:.2f} USDT deinem Guthaben gutgeschrieben.",
        "admin_refund_executor":   "⚖️ Streitfall Auftrag #{id}: Die Mittel wurden dem Auftraggeber zurückerstattet.",
        "admin_refund_resolved":   "🔴 <b>Gelöst: Auftraggeber erstattet.</b>",
        "admin_stats_hdr":         "📊 <b>Admin-Statistiken</b>",
        "admin_stats_users":       "👥 Registrierte Nutzer",
        "admin_stats_tasks":       "📋 Aufträge nach Status",
        "admin_stats_fees":        "💰 Gesamtgebühren",
        "admin_role_client":       "AG",
        "admin_role_executor":     "AN",

        # Direct deal
        "direct_start": (
            "🤝 <b>Neues Direktgeschäft</b>\n\n"
            "Gib den <b>Telegram-Benutzernamen</b> des Auftragnehmers ein, mit dem du zusammenarbeiten möchtest.\n"
            "Bsp: <code>@max_mustermann</code>"
        ),
        "direct_username_err":  "⚠️ Ungültiger Benutzername. Gib einen gültigen Telegram-Benutzernamen ein (z.B. <code>@max_mustermann</code>):",
        "direct_exec_selected": "👤 Ausgewählter Auftragnehmer: <b>{username}</b>",
        "direct_step1":         "📝 <b>Schritt 1/5 — Aufragstitel</b>\n\nSchreibe einen klaren und prägnanten Titel:",
        "direct_title_err":     "⚠️ Der Titel muss zwischen 5 und 200 Zeichen lang sein. Nochmal versuchen:",
        "direct_step2":         "🏷 <b>Schritt 2/5 — Kategorie</b>\n\nWähle die Kategorie des Auftrags:",
        "direct_step3":         "📅 <b>Schritt 3/5 — Frist</b>\n\nGib die Frist ein (z.B. <i>20. Juli 2025</i> oder <i>innerhalb von 5 Tagen</i>):",
        "direct_step4": (
            "📎 <b>Schritt 4/5 — Anhänge</b>\n\n"
            "Sende Dateien, Bilder oder Dokumente (bis zu 50 MB pro Datei).\n"
            "Wenn du fertig bist, drücke <b>⏭ Anhänge überspringen</b>."
        ),
        "direct_file_blocked":  "🚫 Datei <code>{name}</code> nicht erlaubt.",
        "direct_max_att":       "⚠️ Maximal 10 Anhänge. Drücke ⏭ zum Fortfahren.",
        "direct_att_ok":        "✅ Anhang {n}/10 empfangen. Weitere senden oder ⏭ drücken.",
        "direct_file_unknown":  "⚠️ Unbekannter Dateityp.",
        "direct_step5": (
            "💰 <b>Schritt 5/5 — Bruttovergütung</b>\n\n"
            "Gib die Vergütung in <b>USDT</b> ein, die du anbieten möchtest.\n"
            "⚠️ 10% werden als Plattformgebühr einbehalten.\n"
            "90% gehen bei Abschluss an den Auftragnehmer."
        ),
        "direct_reward_err":    "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>20.00</code>):",
        "direct_insufficient": (
            "❌ Unzureichendes Guthaben. Du hast <b>{bal:.2f} USDT</b>, "
            "der Auftrag erfordert jedoch <b>{gross:.2f} USDT</b>.\n"
            "Lade dein Wallet über 💰 Wallet auf."
        ),
        "direct_freeze_err":    "❌ Fehler beim Einfrieren der Mittel. Bitte erneut versuchen.",
        "direct_created": (
            "✅ <b>Direktgeschäft erstellt!</b>\n\n"
            "🆔 Auftrag #{id} — {title}\n"
            "👤 Für: <b>{username}</b>\n"
            "💰 Treuhand eingefroren: <b>{gross:.2f} USDT</b>\n\n"
            "📩 Schicke diesen Link an {username}, damit er/sie den Auftrag annehmen kann:\n"
            "<code>{link}</code>"
        ),
        "direct_invalid_link":  "❌ Ungültiger Link oder Auftrag nicht mehr verfügbar.",
        "direct_own_task":      "⚠️ Du kannst deinen eigenen Auftrag nicht annehmen.",
        "direct_offer": (
            "🤝 <b>Direktgeschäft-Angebot</b>\n\n"
            "📋 <b>{title}</b>\n"
            "🏷 {category} | 📅 {deadline}\n"
            "💰 Nettovergütung für dich: <b>{net:.2f} USDT</b>\n\n"
            "Nimmst du diesen Auftrag an?"
        ),
        "direct_unavailable":   "❌ Auftrag nicht mehr verfügbar.",
        "direct_taken":         "❌ Auftrag bereits vergeben.",
        "direct_accepted_client": (
            "🎉 <b>Direktgeschäft angenommen!</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "Der Auftragnehmer hat dein Angebot angenommen. Der Chat ist jetzt aktiv.\n"
            "Schreibe hier, um anonym zu kommunizieren."
        ),
        "direct_accepted_executor": (
            "✅ <b>Auftrag angenommen!</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "💰 Nettovergütung: <b>{net:.2f} USDT</b>\n\n"
            "Schreibe hier, um anonym mit dem Auftraggeber zu kommunizieren."
        ),
        "direct_already_handled": "❌ Auftrag bereits bearbeitet.",
        "direct_declined_client": (
            "❌ <b>Direktgeschäft abgelehnt</b>\n\n"
            "Auftrag #{id} — {title}\n"
            "Der Auftragnehmer hat das Angebot abgelehnt.\n"
            "💰 <b>{gross:.2f} USDT</b> deinem Guthaben zurückgebucht."
        ),
        "direct_declined_executor": "Du hast den Auftrag <b>{title}</b> abgelehnt.\nDu kannst weitere Aufträge im Kanal erkunden.",
        "direct_cancelled":     "❌ Vorgang abgebrochen.",

        # Payments
        "wallet_hdr":           "💰 <b>Wallet</b>",
        "wallet_avail":         "💵 Verfügbares Guthaben",
        "wallet_frozen":        "🔒 Im Treuhand",
        "wallet_action":        "Aufladen oder auszahlen:",
        "topup_crypto_prompt": (
            "💳 <b>Aufladen via CryptoBot (USDT)</b>\n\n"
            "Gib den USDT-Betrag ein, den du aufladen möchtest (z.B. <code>10.00</code>):"
        ),
        "topup_amount_err":     "⚠️ Ungültiger Betrag. Gib eine positive Zahl ein (z.B. <code>10.00</code>):",
        "topup_crypto_desc":    "Aufladung Fai un Salto — {amount} USDT",
        "topup_pay_btn":        "💳 Zahlen via CryptoBot P2P",
        "topup_invoice_ok": (
            "✅ Rechnung für <b>{amount:.2f} USDT</b> erstellt\n\n"
            "Klicke den Button, um die Zahlung abzuschließen.\n"
            "Das Guthaben wird nach Bestätigung automatisch aktualisiert."
        ),
        "topup_cryptobot_err":  "❌ Fehler beim Erstellen der CryptoBot-Rechnung. Bitte später erneut versuchen.",
        "topup_conn_err":       "⚠️ Verbindungsfehler mit CryptoBot. Bitte erneut versuchen.",
        "topup_stars_prompt": (
            "⭐ <b>Guthaben via Telegram Stars aufladen</b>\n\n"
            "Kurs: 1 Star = {rate} USDT\n"
            "⚠️ Es gilt eine Plattformgebühr von 10% auf die Aufladung.\n\n"
            "Gib den USDT-Betrag ein, den du aufladen möchtest (z.B. <code>5.00</code>):"
        ),
        "topup_stars_title":    "Wallet-Guthaben aufladen",
        "topup_stars_desc":     "{amount:.2f} USDT auf Fai un Salto aufladen (inkl. 10% Gebühr)",
        "topup_stars_label":    "Stars",
        "stars_task_missing":   "⚠️ Auftragsdaten nicht gefunden. Deine Stars sind sicher — bitte Support kontaktieren.",
        "stars_task_ok": (
            "⭐ <b>Stars-Zahlung bestätigt!</b>\n\n"
            "🆔 Auftrag #{id} — {title}\n"
            "⭐ Gezahlte Stars: <b>{stars}</b>\n"
            "💰 Treuhand eingefroren: <b>{gross:.2f} USDT</b>\n\n"
            "Der Auftrag ist jetzt im Kanal sichtbar."
        ),
        "stars_topup_ok": (
            "⭐ <b>Aufladung abgeschlossen!</b>\n\n"
            "Gezahlte Stars: <b>{stars}</b>\n"
            "Bruttowert: {gross:.4f} USDT\n"
            "Gebühr (10%): -{fee:.4f} USDT\n"
            "💵 <b>Gutgeschrieben: {net:.4f} USDT</b>"
        ),
        "withdrawal_hdr":       "💸 <b>Auszahlung</b>\n\nVerwendung: <code>/prelievo &lt;Betrag&gt;</code>\nBsp: <code>/prelievo 10.00</code>",
        "withdrawal_inv":       "⚠️ Ungültiger Betrag. Verwende: <code>/prelievo 10.00</code>",
        "withdrawal_insuf":     "❌ Unzureichendes Guthaben. Verfügbar: <b>{bal:.2f} USDT</b>, angefordert: <b>{amount:.2f} USDT</b>.",
        "withdrawal_tx_err":    "❌ Transaktionsfehler. Bitte erneut versuchen.",
        "withdrawal_comment":   "Auszahlung Fai un Salto",
        "withdrawal_ok":        "✅ <b>Auszahlung bestätigt!</b>\n\n💸 <b>{amount:.2f} USDT</b> an dein CryptoBot-Wallet überwiesen.",
        "withdrawal_net_err":   "⚠️ CryptoBot-Netzwerkfehler. Der Betrag wurde deinem internen Guthaben zurückgebucht.",

        # Rating
        "rating_labels": {1: "😞 Sehr schlecht", 2: "😐 Schlecht", 3: "🙂 Ausreichend", 4: "😊 Gut", 5: "🌟 Ausgezeichnet"},
        "rate_exec_prompt":     "⭐ <b>Wie lief der Deal?</b>\nBewerte den Auftragnehmer:",
        "rate_client_prompt":   "⭐ <b>Wie lief der Deal?</b>\nBewerte den Auftraggeber:",
        "rated_exec":           "⭐ Du hast den Auftragnehmer mit <b>{stars}</b> bewertet — {label}\nDanke für dein Feedback!",
        "rated_client":         "⭐ Du hast den Auftraggeber mit <b>{stars}</b> bewertet — {label}\nDanke für dein Feedback!",
        "rating_not_found":     "❌ Auftrag nicht gefunden.",
        "rating_only_client":   "❌ Nur der Auftraggeber kann den Auftragnehmer bewerten.",
        "rating_only_executor": "❌ Nur der Auftragnehmer kann den Auftraggeber bewerten.",
        "rating_no_executor":   "❌ Kein Auftragnehmer zu bewerten.",

        # CryptoBot poller
        "cryptobot_topup_ok":   "✅ <b>Aufladung erhalten!</b>\n\n💵 <b>{amount:.4f} USDT</b> deinem Guthaben gutgeschrieben.",
    },
}


async def get_lang(user_id: int, context) -> str:
    """Return cached language or load it from DB."""
    if "lang" in context.user_data:
        return context.user_data["lang"]
    import database as db
    lang = await db.get_user_language(user_id)
    context.user_data["lang"] = lang
    return lang


def all_cancel_texts() -> set[str]:
    return {STRINGS[l]["btn_cancel"] for l in STRINGS}


def all_skip_texts() -> set[str]:
    return {STRINGS[l]["btn_skip_attachments"] for l in STRINGS}
