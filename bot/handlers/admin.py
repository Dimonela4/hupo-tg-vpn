from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from bot.database import Database
from bot.keyboards import admin_kb
from bot.services.xray import xray_service

router = Router()


class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_user_id = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_kb())

@router.message(Command("debug-delete"))
async def debug_delete(message: Message, db: Database):
    if not is_admin(message.from_user.id):
        return
    if (message.text or "").strip() != "/debug-delete CONFIRM":
        await message.answer("Для подтверждения отправьте: /debug-delete CONFIRM")
        return
    await db.debug_delete_all_users()
    await message.answer("Все пользователи удалены из базы данных.")

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, db: Database):
    if not is_admin(callback.from_user.id):
        return
    stats = await db.get_user_count()
    text = (
        "📊 <b>Статистика:</b>\n\n"
        f"👥 Всего пользователей: <b>{stats}</b>\n"
    )
    try:
        await callback.message.edit_text(text, reply_markup=admin_kb())
    except:
        return

@router.callback_query(F.data == "admin:add_user")
async def admin_add_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.answer("Введите ID пользователя для добавления (для отмены ввести /otmena):")
    await state.set_state(AdminStates.waiting_user_id)

@router.message(AdminStates.waiting_user_id)
async def admin_do_add_user(message: Message, state: FSMContext, db: Database):
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/otmena":
        await state.clear()
        await message.answer(
            f"❌ Отмена добавления пользователя",
            reply_markup=admin_kb()
        )
        return

    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("⚠️ Введите корректный числовой ID.")
        return

    try:
        await xray_service.extend_client(tg_id=user_id, days=7)
        await db.add_user(
            tg_id=user_id,
            first_name=message.from_user.first_name,
            second_name=message.from_user.last_name,
            nickname=message.from_user.username,
        )
    except Exception:
        await message.answer("Не удалось создать клиента в панели. Проверьте ID и попробуйте снова.")
        return
    
    await state.clear()
    await message.answer(
        f"✅ Пользователь {user_id} добавлен в базу.",
        reply_markup=admin_kb()
    )

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.answer("📢 Отправь сообщение для рассылки (для отмены ввести /otmena):")
    await state.set_state(AdminStates.waiting_broadcast)

@router.message(AdminStates.waiting_broadcast)
async def admin_do_broadcast(message: Message, state: FSMContext, db: Database):
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/otmena":
        await state.clear()
        await message.answer(
            f"❌ Отмена рассылки",
            reply_markup=admin_kb()
        )
        return

    # Получаем всех пользователей

    user_ids = await db.get_all_tg_ids()

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена.\n"
        f"Отправлено: {sent}, не доставлено: {failed}",
        reply_markup=admin_kb(),
    )
