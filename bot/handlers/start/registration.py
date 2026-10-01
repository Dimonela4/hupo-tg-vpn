from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.database import Database
from bot.keyboards import main_menu_kb
from bot.services.bonus import issue_bonus_key
from bot.texts.start import WELCOME_TEXT

router = Router()
REFERRAL_BONUS_DAYS = 7
BASE_BONUS_DAYS = 4


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, bot):
    user = message.from_user
    existing_user = await db.get_user(user.id)
    if existing_user is None:
        referrer_id = None
        args = (message.text or "").split(maxsplit=1)
        if len(args) == 2 and args[1].startswith("ref_"):
            try:
                candidate_id = int(args[1][4:])
                if candidate_id != user.id and await db.get_user(candidate_id):
                    referrer_id = candidate_id
            except ValueError:
                pass

        is_referral = referrer_id is not None
        granted = await issue_bonus_key(
            user_id=user.id,
            db=db,
            bot=bot,
            days=REFERRAL_BONUS_DAYS if is_referral else BASE_BONUS_DAYS,
            reason=(
                "Вы перешли по реферальной ссылке!"
                if is_referral
                else f"Подарок за регистрацию: {BASE_BONUS_DAYS} дня доступа."
            ),
            referrer_id=referrer_id,
            first_name=user.first_name,
            second_name=user.last_name,
            nickname=user.username,
        )
        if granted and referrer_id is not None:
            await issue_bonus_key(
                user_id=referrer_id,
                db=db,
                bot=bot,
                days=REFERRAL_BONUS_DAYS,
                reason="Ваш друг зарегистрировался по вашей ссылке!",
            )

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
