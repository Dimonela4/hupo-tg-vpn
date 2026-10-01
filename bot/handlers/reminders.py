import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database import Database
from bot.services.xray import xray_service

logger = logging.getLogger(__name__)


async def check_expiring_keys(bot: Bot, db: Database) -> None:
    now_ms = int(datetime.now().timestamp() * 1000)
    for user_id in await db.get_all_tg_ids():
        try:
            records = await xray_service.get_client_info(user_id)
            for record in records:
                client = record.get("client", record)
                sub_id = client.get("subId")
                expiry_ms = int(client.get("expiryTime", 0) or 0)
                if not sub_id or expiry_ms <= 0:
                    continue
                days_left = (expiry_ms - now_ms) // 86_400_000
                if days_left not in {5, 3, 1, 0}:
                    continue
                if await db.reminder_was_sent(user_id, sub_id, days_left, expiry_ms):
                    continue
                expiry_date = datetime.fromtimestamp(expiry_ms / 1000)
                await send_reminder(bot, user_id, int(days_left), expiry_date)
                await db.mark_reminder_sent(user_id, sub_id, int(days_left), expiry_ms)
        except Exception:
            logger.exception("Could not check expiring keys for user %s", user_id)


async def send_reminder(
    bot: Bot, user_id: int, days_left: int, expiry_date: datetime
) -> None:
    if days_left == 5:
        text = f"🔔 VPN-ключ истекает через 5 дней.\n📅 {expiry_date:%d.%m.%Y}"
    elif days_left == 3:
        text = f"⚠️ VPN-ключ истекает через 3 дня.\n📅 {expiry_date:%d.%m.%Y}"
    elif days_left == 1:
        text = f"🚨 VPN-ключ истекает завтра.\n📅 {expiry_date:%d.%m.%Y}"
    elif days_left == 0:
        text = f"⏰ VPN-ключ истекает сегодня в {expiry_date:%H:%M}."
    else:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить ключ", callback_data="buy")],
        [InlineKeyboardButton(text="🔑 Мои ключи", callback_data="my_keys")],
    ])
    await bot.send_message(user_id, text, reply_markup=keyboard)


async def reminders_task(bot: Bot, db: Database) -> None:
    while True:
        try:
            await check_expiring_keys(bot, db)
        except Exception:
            logger.exception("Reminder scan failed")
        await asyncio.sleep(3600)
