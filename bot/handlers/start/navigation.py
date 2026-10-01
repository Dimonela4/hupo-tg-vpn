from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_kb
from bot.texts.start import WELCOME_TEXT

router = Router()

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu_kb(),
    )

    await callback.answer()