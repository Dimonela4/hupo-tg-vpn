from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import PLANS


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Купить ключ", callback_data="buy")
    builder.button(text="🔑 Мои ключи", callback_data="my_keys")
    builder.button(text="👥 Пригласить друга", callback_data="referral")
    builder.button(text="ℹ️ Как подключиться", callback_data="howto")
    builder.button(text="📄 Договор оферты", callback_data="offer")
    builder.button(text="💬 Поддержка", url="https://t.me/buntuus")
    builder.adjust(2, 1, 1, 1, 1)
    return builder.as_markup()


def plans_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan_id, plan in PLANS.items():
        builder.button(
            text=f"{plan['label']} — {plan['rub']:.2f} ₽",
            callback_data=f"plan:{plan_id}"
        )
    builder.button(text="◀️ Назад", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin:stats")
    builder.button(text="📢 Рассылка", callback_data="admin:broadcast")
    builder.button(text="Добавить пользователя", callback_data="admin:add_user")
    builder.adjust(1)
    return builder.as_markup()


def back_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В главное меню", callback_data="back_main")
    return builder.as_markup()

def back_create_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Купить ключ", callback_data="buy")
    builder.button(text="◀️ В главное меню", callback_data="back_main")
    return builder.as_markup()


def key_actions_kb(sub_id: str, key_num: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔗 Показать ссылку #{key_num}", callback_data=f"renew_key:{sub_id}")
    builder.button(text="◀️ В главное меню", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()
