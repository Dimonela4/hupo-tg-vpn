import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.database import Database
from bot.handlers import buy, keys, admin
from bot.handlers.start import router as start_router
from bot.handlers.reminders import reminders_task
from bot.services.xray import xray_service
from bot.yookassa_payment import poll_payment_orders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    db = Database(settings.DATABASE_URL)
    await db.init()

    dp["db"] = db

    dp.include_router(start_router)
    dp.include_router(buy.router)
    dp.include_router(keys.router)
    dp.include_router(admin.router)

    background_tasks = [
        asyncio.create_task(poll_payment_orders(bot, db)),
        asyncio.create_task(reminders_task(bot, db)),
    ]
    try:
        logger.info("Бот запущен")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await db.close()
        await xray_service.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
