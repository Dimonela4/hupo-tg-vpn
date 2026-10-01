import asyncpg
from typing import Optional


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def init(self):
        """Подключение к PostgreSQL и создание таблицы."""

        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=1,
            max_size=10
        )

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tg_users (
                    id BIGSERIAL PRIMARY KEY,
                    tg_id BIGINT NOT NULL UNIQUE,

                    first_name TEXT,
                    second_name TEXT,
                    nickname TEXT,

                    referred_id BIGINT,

                    first_chat TIMESTAMP DEFAULT NOW(),

                    key_given BOOLEAN DEFAULT FALSE
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payment_orders (
                    id BIGSERIAL PRIMARY KEY,
                    payment_id TEXT NOT NULL UNIQUE,
                    tg_id BIGINT NOT NULL REFERENCES tg_users(tg_id),
                    plan_id TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
                    currency TEXT NOT NULL DEFAULT 'RUB',
                    status TEXT NOT NULL DEFAULT 'pending',
                    grant_expiry_ms BIGINT,
                    fulfilled_at TIMESTAMPTZ,
                    notified_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS payment_orders_pending_idx
                ON payment_orders (status, fulfilled_at)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_reminders (
                    tg_id BIGINT NOT NULL,
                    sub_id TEXT NOT NULL,
                    days_left INTEGER NOT NULL,
                    expiry_ms BIGINT NOT NULL,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tg_id, sub_id, days_left, expiry_ms)
                )
            """)

    async def close(self):
        """Закрытие соединения с БД."""

        if self.pool:
            await self.pool.close()

    async def add_user(
        self,
        tg_id: int,
        first_name: str | None = None,
        second_name: str | None = None,
        nickname: str | None = None,
        referred_id: int | None = None
    ) -> bool:
        """
        Добавляет пользователя в базу.

        Возвращает:
            True  — пользователь добавлен
            False — пользователь уже существует
        """

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO tg_users (
                    tg_id,
                    first_name,
                    second_name,
                    nickname,
                    referred_id
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (tg_id) DO NOTHING
                RETURNING id
                """,
                tg_id,
                first_name,
                second_name,
                nickname,
                referred_id
            )

            return result is not None

    async def get_referral_count(self, tg_id: int) -> int:
        """Возвращает количество приглашённых пользователем tg_id."""

        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM tg_users
                WHERE referred_id = $1
                """,
                tg_id
            )

    async def key_given(self, tg_id: int) -> bool:
        """Выставляет флаг key_given для пользователя tg_id в TRUE, если ключ был выдан."""

        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                UPDATE tg_users
                SET key_given = TRUE
                WHERE tg_id = $1
                RETURNING key_given
                """,
                tg_id
            )

    # =========================================================
    # 1. ПРОВЕРКА РЕФЕРАЛА
    # =========================================================

    async def check_referral(self, tg_id: int) -> Optional[int]:
        """
        Возвращает ID пользователя, который пригласил tg_id.

        Если реферала нет — возвращает None.
        """

        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT referred_id
                FROM tg_users
                WHERE tg_id = $1
                """,
                tg_id
            )

    # =========================================================
    # 2. КОЛИЧЕСТВО ПОЛЬЗОВАТЕЛЕЙ
    # =========================================================

    async def get_user_count(self) -> int:
        """Возвращает количество пользователей."""

        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM tg_users
                """
            )

    async def get_all_tg_ids(self) -> list[int]:
        """Возвращает список всех tg_id пользователей."""

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT tg_id
                FROM tg_users
                """
            )
            return [row["tg_id"] for row in rows]

    async def debug_delete_all_users(self) -> None:
        """Удаляет всех пользователей из базы. Только для отладки!"""

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM payment_orders")
                await conn.execute("DELETE FROM sent_reminders")
                await conn.execute("DELETE FROM tg_users")

    # =========================================================
    # 3. ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ
    # =========================================================

    async def get_user(self, tg_id: int) -> Optional[dict]:
        """
        Возвращает информацию о пользователе.

        Если пользователя нет — возвращает None.
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id,
                    tg_id,
                    first_name,
                    second_name,
                    nickname,
                    referred_id,
                    first_chat,
                    key_given
                FROM tg_users
                WHERE tg_id = $1
                """,
                tg_id
            )

            if row is None:
                return None

            return dict(row)

    async def save_payment(
        self,
        user_id: int,
        payment_id: str,
        amount_minor: int,
        plan_id: str,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO payment_orders (payment_id, tg_id, plan_id, amount_minor)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (payment_id) DO NOTHING
                """,
                payment_id, user_id, plan_id, amount_minor,
            )

    async def get_payment(self, payment_id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM payment_orders WHERE payment_id = $1", payment_id
            )
            return dict(row) if row else None

    async def get_unfinished_payments(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM payment_orders
                WHERE (status NOT IN ('canceled', 'amount_mismatch', 'failed')
                       AND fulfilled_at IS NULL)
                   OR (status = 'succeeded' AND notified_at IS NULL)
                ORDER BY created_at
                """
            )
            return [dict(row) for row in rows]

    async def update_payment_status(self, payment_id: str, status: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE payment_orders
                SET status = $2, updated_at = NOW()
                WHERE payment_id = $1 AND fulfilled_at IS NULL
                """,
                payment_id, status,
            )

    async def set_payment_grant_expiry(self, payment_id: str, expiry_ms: int) -> int:
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                UPDATE payment_orders
                SET grant_expiry_ms = COALESCE(grant_expiry_ms, $2),
                    updated_at = NOW()
                WHERE payment_id = $1
                RETURNING grant_expiry_ms
                """,
                payment_id, expiry_ms,
            )
            if value is None:
                raise ValueError(f"Unknown payment {payment_id}")
            return value

    async def mark_payment_fulfilled(self, payment_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE payment_orders
                SET status = 'succeeded', fulfilled_at = COALESCE(fulfilled_at, NOW()),
                    updated_at = NOW()
                WHERE payment_id = $1
                """,
                payment_id,
            )

    async def mark_payment_notified(self, payment_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE payment_orders SET notified_at = NOW(), updated_at = NOW() WHERE payment_id = $1",
                payment_id,
            )

    async def reminder_was_sent(
        self, tg_id: int, sub_id: str, days_left: int, expiry_ms: int
    ) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM sent_reminders
                    WHERE tg_id = $1 AND sub_id = $2
                      AND days_left = $3 AND expiry_ms = $4
                )
                """,
                tg_id, sub_id, days_left, expiry_ms,
            )

    async def mark_reminder_sent(
        self, tg_id: int, sub_id: str, days_left: int, expiry_ms: int
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sent_reminders (tg_id, sub_id, days_left, expiry_ms)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
                """,
                tg_id, sub_id, days_left, expiry_ms,
            )
