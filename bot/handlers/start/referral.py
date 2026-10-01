from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import Database
from bot.keyboards import back_main_kb
from bot.texts.start import WELCOME_TEXT

router = Router()

REFERRAL_BONUS_DAYS = 7


@router.callback_query(F.data == "referral")
async def referral_info(
    callback: CallbackQuery,
    db: Database,
    bot,
):
    user_id = callback.from_user.id

    bot_info = await bot.get_me()

    ref_link = (
        f"https://t.me/{bot_info.username}"
        f"?start=ref_{user_id}"
    )

    count = await db.get_referral_count(user_id)

    await callback.message.edit_text(
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получайте по "
        f"<b>{REFERRAL_BONUS_DAYS} дней защищённого "
        f"соединения бесплатно!</b>\n\n"
        f"Твоя ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"👤 Приглашено друзей: <b>{count}</b>",
        reply_markup=back_main_kb(),
    )

    await callback.answer()