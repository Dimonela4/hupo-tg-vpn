from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import PLANS
from bot.database import Database
from bot.keyboards import plans_kb
from bot.yookassa_payment import create_payment

router = Router()


@router.callback_query(F.data == "buy")
@router.message(Command("plan"))
async def show_plans(event: CallbackQuery | Message):
    text = (
        "💎 <b>Выберите тариф:</b>\n\n"
        "• Протокол <b>VLESS Reality</b>\n"
        "• Безлимитный трафик\n"
        "• До 3 устройств\n\n"
        "Оплата означает согласие с договором оферты в главном меню."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=plans_kb())
        await event.answer()
    else:
        await event.answer(text, reply_markup=plans_kb())


@router.callback_query(F.data.startswith("plan:"))
async def select_plan(callback: CallbackQuery, db: Database):
    plan_id = callback.data.partition(":")[2]
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    user = callback.from_user
    await db.add_user(
        tg_id=user.id,
        first_name=user.first_name,
        second_name=user.last_name,
        nickname=user.username,
    )
    try:
        payment = await create_payment(
            user_id=user.id,
            amount_minor=plan["amount_minor"],
            plan_id=plan_id,
            description=f"Доступ к VPN на {plan['days']} дней",
            db=db,
        )
    except Exception:
        await callback.answer("Не удалось создать оплату. Попробуйте позже.", show_alert=True)
        return

    await callback.message.edit_text(
        f"💳 Тариф: {plan['label']}\n"
        f"Сумма: {plan['rub']:.2f} ₽\n\n"
        "Оплатите заказ по кнопке ниже. После оплаты статус проверяется автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Оплатить через YooKassa", url=payment["url"])
        ]]),
    )
    await callback.answer()
