import html
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import back_create_kb, back_main_kb, key_actions_kb
from bot.services.xray import xray_service

router = Router()


@router.callback_query(F.data == "my_keys")
@router.message(Command("profile"))
async def my_keys(event: CallbackQuery | Message):
    user_id = event.from_user.id
    try:
        records = await xray_service.get_client_info(user_id)
    except Exception:
        text = "Не удалось получить ключи сейчас. Попробуйте позже или напишите в поддержку."
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=back_main_kb())
            await event.answer()
        else:
            await event.answer(text, reply_markup=back_main_kb())
        return
    if not records:
        text = "🔑 У вас пока нет активных ключей.\n\nНажмите <b>Купить ключ</b>, чтобы приобрести."
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=back_create_kb())
            await event.answer()
        else:
            await event.answer(text, reply_markup=back_create_kb())
        return

    if isinstance(event, CallbackQuery):
        await event.message.edit_text("🔐 <b>Ваши VPN-ключи:</b>")
        send = event.message.answer
        await event.answer()
    else:
        await event.answer("🔐 <b>Ваши VPN-ключи:</b>")
        send = event.answer

    for number, record in enumerate(records, 1):
        client = record.get("client", record)
        sub_id = client.get("subId")
        if not sub_id:
            continue
        key_link = await xray_service.get_user_key(user_id, sub_id)
        expiry_ms = int(client.get("expiryTime", 0) or 0)
        expiry_text = (
            "Без срока действия"
            if expiry_ms <= 0
            else datetime.fromtimestamp(expiry_ms / 1000).strftime("%d.%m.%Y")
        )
        days_left = (
            "∞"
            if expiry_ms <= 0
            else str(max((expiry_ms - int(datetime.now().timestamp() * 1000)) // 86_400_000, 0))
        )
        max_hwid = int(client.get("limitHwid", 3) or 3)
        await send(
            f"🔑 <b>Ключ #{number}</b>\n"
            f"📅 Действует до: <b>{expiry_text}</b>\n"
            f"⏳ Осталось дней: <b>{days_left}</b>\n"
            f"📱 Лимит устройств: <b>{max_hwid}</b>\n\n"
            f"🔗 <b>Ссылка:</b>\n<code>{html.escape(key_link or '')}</code>",
            reply_markup=key_actions_kb(sub_id, number),
        )


@router.callback_query(F.data.startswith("renew_key:"))
async def refresh_key(callback: CallbackQuery):
    sub_id = callback.data.partition(":")[2]
    try:
        link = await xray_service.get_user_key(callback.from_user.id, sub_id)
    except Exception:
        await callback.answer("Не удалось получить ключ. Попробуйте позже.", show_alert=True)
        return
    if not link:
        await callback.answer("Ключ не найден", show_alert=True)
        return
    await callback.message.edit_text(
        f"🔑 <b>Ссылка на ключ:</b>\n<code>{link}</code>",
        reply_markup=back_main_kb(),
    )
    await callback.answer()
