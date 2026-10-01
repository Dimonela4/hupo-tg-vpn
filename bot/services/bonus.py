import html
import logging

from bot.database import Database
from bot.services.xray import xray_service

logger = logging.getLogger(__name__)


async def issue_bonus_key(
    user_id: int,
    db: Database,
    bot,
    days: int,
    reason: str,
    referrer_id: int | None = None,
    first_name: str | None = None,
    second_name: str | None = None,
    nickname: str | None = None,
) -> bool:
    try:
        result = await xray_service.extend_client(days=days, tg_id=user_id)
        key = await xray_service.get_user_key(user_id)
        if not key:
            raise RuntimeError("3X-UI did not return a subscription link")
        await db.add_user(
            tg_id=user_id,
            referred_id=referrer_id,
            first_name=first_name,
            second_name=second_name,
            nickname=nickname,
        )
        await bot.send_message(
            user_id,
            f"🎁 <b>{reason}</b>\n\n"
            f"Ваш ключ продлён на <b>{days} дней</b>.\n"
            f"📅 Действует до: <b>{result['new_expiry_time']}</b>\n\n"
            f"🔑 <code>{html.escape(key)}</code>",
        )
        await db.key_given(user_id)
        return True
    except Exception:
        logger.exception("Could not issue bonus for Telegram user %s", user_id)
        return False
