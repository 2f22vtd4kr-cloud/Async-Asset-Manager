import aiosqlite
import json
import logging
from typing import Optional

DB_PATH = "fai_un_salto.db"
logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                client_rating REAL DEFAULT 5.0,
                executor_rating REAL DEFAULT 5.0,
                client_reviews_count INTEGER DEFAULT 0,
                executor_reviews_count INTEGER DEFAULT 0,
                balance_usdt REAL DEFAULT 0.0,
                frozen_usdt REAL DEFAULT 0.0,
                is_blocked INTEGER DEFAULT 0,
                is_shadow_banned INTEGER DEFAULT 0,
                disputes_initiated INTEGER DEFAULT 0,
                disputes_lost INTEGER DEFAULT 0,
                total_tasks_client INTEGER DEFAULT 0,
                total_tasks_executor INTEGER DEFAULT 0,
                notification_categories TEXT DEFAULT '[]',
                language TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_message_id INTEGER DEFAULT NULL,
                client_id INTEGER,
                executor_id INTEGER DEFAULT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                deadline TEXT,
                category TEXT DEFAULT 'Generale',
                attachments TEXT DEFAULT NULL,
                reward_gross REAL NOT NULL,
                reward_net REAL NOT NULL,
                status TEXT CHECK(status IN ('open','in_progress','completed','dispute','cancelled')),
                is_direct INTEGER DEFAULT 0,
                target_executor_identity TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claimed_at TIMESTAMP DEFAULT NULL,
                completed_at TIMESTAMP DEFAULT NULL,
                disputed_at TIMESTAMP DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS deal_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER UNIQUE,
                client_id INTEGER,
                executor_id INTEGER,
                room_token TEXT UNIQUE,
                status TEXT CHECK(status IN ('active','closed','disputed')),
                initialized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS deal_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                sender_id INTEGER,
                message_type TEXT,
                file_id TEXT DEFAULT NULL,
                content_preview TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admin_revenue (
                id INTEGER PRIMARY KEY DEFAULT 1,
                total_collected_fees REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_executor ON tasks(executor_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON deal_sessions(room_token);
        """)
        # Ensure admin_revenue row exists
        await db.execute(
            "INSERT OR IGNORE INTO admin_revenue (id, total_collected_fees) VALUES (1, 0.0)"
        )
        await db.commit()
        # Migration: add language column to existing databases
        try:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT NULL")
            await db.commit()
        except Exception:
            pass  # Column already exists
    logger.info("Database initialized.")


async def get_or_create_user(telegram_id: int, username: Optional[str] = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row)


async def get_user_language(telegram_id: int) -> Optional[str]:
    """Return the stored language code or None if not yet set."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT language FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return row[0]  # may be None if column is NULL


async def set_user_language(telegram_id: int, lang: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language = ? WHERE telegram_id = ?", (lang, telegram_id)
        )
        await db.commit()


async def get_user(telegram_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def freeze_funds(telegram_id: int, amount: float) -> bool:
    """Atomically move `amount` from balance_usdt to frozen_usdt."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("BEGIN")
            async with db.execute(
                "SELECT balance_usdt FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or row[0] < amount:
                await db.execute("ROLLBACK")
                return False
            await db.execute(
                "UPDATE users SET balance_usdt = balance_usdt - ?, frozen_usdt = frozen_usdt + ? WHERE telegram_id = ?",
                (amount, amount, telegram_id),
            )
            await db.execute("COMMIT")
            return True
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def release_to_executor(task_id: int) -> bool:
    """90/10 escrow split: 90% to executor, 10% to admin_revenue."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("BEGIN")
            async with db.execute(
                "SELECT client_id, executor_id, reward_gross FROM tasks WHERE task_id = ?",
                (task_id,),
            ) as cursor:
                task = await cursor.fetchone()
            if not task:
                await db.execute("ROLLBACK")
                return False
            gross = task["reward_gross"]
            executor_share = round(gross * 0.90, 8)
            platform_fee = round(gross * 0.10, 8)
            # Unfreeze from client
            await db.execute(
                "UPDATE users SET frozen_usdt = frozen_usdt - ? WHERE telegram_id = ?",
                (gross, task["client_id"]),
            )
            # Credit executor
            await db.execute(
                "UPDATE users SET balance_usdt = balance_usdt + ?, total_tasks_executor = total_tasks_executor + 1 WHERE telegram_id = ?",
                (executor_share, task["executor_id"]),
            )
            # Platform fee
            await db.execute(
                "UPDATE admin_revenue SET total_collected_fees = total_collected_fees + ? WHERE id = 1",
                (platform_fee,),
            )
            # Update task
            await db.execute(
                "UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (task_id,),
            )
            await db.execute("COMMIT")
            return True
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def refund_client(task_id: int) -> bool:
    """Full rollback: return 100% gross to client balance_usdt."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("BEGIN")
            async with db.execute(
                "SELECT client_id, executor_id, reward_gross FROM tasks WHERE task_id = ?",
                (task_id,),
            ) as cursor:
                task = await cursor.fetchone()
            if not task:
                await db.execute("ROLLBACK")
                return False
            gross = task["reward_gross"]
            await db.execute(
                "UPDATE users SET frozen_usdt = frozen_usdt - ?, balance_usdt = balance_usdt + ? WHERE telegram_id = ?",
                (gross, gross, task["client_id"]),
            )
            await db.execute(
                "UPDATE tasks SET status = 'cancelled' WHERE task_id = ?", (task_id,)
            )
            await db.execute("COMMIT")
            return True
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def credit_balance(telegram_id: int, amount: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance_usdt = balance_usdt + ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await db.commit()


async def debit_balance(telegram_id: int, amount: float) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("BEGIN")
            async with db.execute(
                "SELECT balance_usdt FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or row[0] < amount:
                await db.execute("ROLLBACK")
                return False
            await db.execute(
                "UPDATE users SET balance_usdt = balance_usdt - ? WHERE telegram_id = ?",
                (amount, telegram_id),
            )
            await db.execute("COMMIT")
            return True
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def add_admin_fee(amount: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE admin_revenue SET total_collected_fees = total_collected_fees + ? WHERE id = 1",
            (amount,),
        )
        await db.commit()


async def log_deal_message(
    task_id: int,
    sender_id: int,
    message_type: str,
    content_preview: str,
    file_id: Optional[str] = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO deal_messages (task_id, sender_id, message_type, file_id, content_preview) VALUES (?,?,?,?,?)",
            (task_id, sender_id, message_type, file_id, content_preview),
        )
        await db.commit()


async def get_task(task_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_session_by_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM deal_sessions WHERE (client_id = ? OR executor_id = ?) AND status = 'active'",
            (user_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_session_by_task(task_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM deal_sessions WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_deal_session(
    task_id: int, client_id: int, executor_id: int, room_token: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO deal_sessions (task_id, client_id, executor_id, room_token, status) VALUES (?,?,?,?,'active')",
            (task_id, client_id, executor_id, room_token),
        )
        await db.commit()


async def close_deal_session(task_id: int, status: str = "closed") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE deal_sessions SET status = ? WHERE task_id = ?", (status, task_id)
        )
        await db.commit()


async def get_deal_messages(task_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM deal_messages WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_tasks_as_client(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE client_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_tasks_as_executor(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE executor_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_rating(telegram_id: int, role: str, new_star: int) -> None:
    """Weighted running-average update of client_rating or executor_rating."""
    col_r = f"{role}_rating"
    col_c = f"{role}_reviews_count"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT {col_r}, {col_c} FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return
        current, count = row
        new_count = count + 1
        new_rating = round((current * count + new_star) / new_count, 2)
        await db.execute(
            f"UPDATE users SET {col_r} = ?, {col_c} = ? WHERE telegram_id = ?",
            (new_rating, new_count, telegram_id),
        )
        await db.commit()


async def freeze_funds_direct(telegram_id: int, amount: float) -> None:
    """Increment frozen_usdt directly (used when payment bypasses the internal balance)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET frozen_usdt = frozen_usdt + ?, "
            "total_tasks_client = total_tasks_client + 1 WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await db.commit()


async def flag_user_if_needed(telegram_id: int) -> None:
    """Shadow-ban user if dispute ratio > 30% or disputes_lost >= 3."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT disputes_initiated, disputes_lost, total_tasks_client, total_tasks_executor FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return
        initiated, lost, tc, te = row
        total = tc + te
        ratio = initiated / total if total > 0 else 0
        if ratio > 0.30 or lost >= 3:
            await db.execute(
                "UPDATE users SET is_shadow_banned = 1 WHERE telegram_id = ?",
                (telegram_id,),
            )
            await db.commit()
            logger.warning("User %s shadow-banned (ratio=%.2f, lost=%d)", telegram_id, ratio, lost)
