"""YooKassa checkout and restart-safe payment status polling."""

from __future__ import annotations

import asyncio
import html
import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from bot.config import PLANS, settings
from bot.services.xray import xray_service

if TYPE_CHECKING:
    from bot.database import Database

logger = logging.getLogger(__name__)

_user_locks: dict[int, asyncio.Lock] = {}


def _payment_api():
    from yookassa import Configuration, Payment

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return Payment


async def create_payment(
    user_id: int,
    amount_minor: int,
    plan_id: str,
    description: str,
    db: Database,
) -> dict:
    if plan_id not in PLANS or PLANS[plan_id]["amount_minor"] != amount_minor:
        raise ValueError("Payment amount does not match the selected plan")

    amount = f"{Decimal(amount_minor) / 100:.2f}"
    payment_api = _payment_api()
    payment = await asyncio.to_thread(
        payment_api.create,
        {
            "amount": {"value": amount, "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/hupovpnbot",
            },
            "capture": True,
            "description": description,
            "metadata": {"tg_id": str(user_id), "plan_id": plan_id},
        },
        uuid.uuid4(),
    )

    await db.save_payment(
        user_id=user_id,
        payment_id=payment.id,
        amount_minor=amount_minor,
        plan_id=plan_id,
    )
    return {"url": payment.confirmation.confirmation_url, "pay_id": payment.id}


async def _notify_payment(payment_row: dict, bot) -> None:
    plan = PLANS[payment_row["plan_id"]]
    key_link = await xray_service.get_user_key(payment_row["tg_id"])
    if not key_link:
        raise RuntimeError("Paid user's subscription link is unavailable")
    expires = xray_service.calculate_date_beauty(payment_row["grant_expiry_ms"])
    await bot.send_message(
        payment_row["tg_id"],
        f"✅ <b>Оплата прошла!</b> Спасибо за покупку.\n\n"
        f"📦 Тариф: {plan['label']}\n"
        f"📅 Действует до: <b>{expires}</b>\n\n"
        f"🔑 <b>Ваш ключ:</b>\n<code>{html.escape(key_link)}</code>",
    )


async def _fulfill(payment_row: dict, db: Database, bot) -> None:
    user_id = payment_row["tg_id"]
    lock = _user_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        payment_row = await db.get_payment(payment_row["payment_id"])
        if payment_row["fulfilled_at"] is None:
            target_expiry = payment_row["grant_expiry_ms"]
            if target_expiry is None:
                current_expiry = await xray_service.get_expiry_date(user_id)
                target_expiry = xray_service.calculate_date(
                    PLANS[payment_row["plan_id"]]["days"],
                    current_expiry or 0,
                )
                target_expiry = await db.set_payment_grant_expiry(
                    payment_row["payment_id"], target_expiry
                )
            await xray_service.set_expiry(user_id, target_expiry)
            await db.mark_payment_fulfilled(payment_row["payment_id"])
            payment_row = await db.get_payment(payment_row["payment_id"])

        if payment_row["notified_at"] is None:
            await _notify_payment(payment_row, bot)
            await db.mark_payment_notified(payment_row["payment_id"])


async def _check_payment(payment_row: dict, db: Database, bot) -> None:
    if payment_row["status"] == "succeeded":
        await _fulfill(payment_row, db, bot)
        return

    payment = await asyncio.to_thread(
        _payment_api().find_one, payment_row["payment_id"]
    )
    status = getattr(payment, "status", None)
    if status != "succeeded":
        if status and status != payment_row["status"]:
            await db.update_payment_status(payment_row["payment_id"], status)
        return

    paid_amount = getattr(getattr(payment, "amount", None), "value", None)
    paid_currency = getattr(getattr(payment, "amount", None), "currency", None)
    expected_amount = f"{Decimal(payment_row['amount_minor']) / 100:.2f}"
    try:
        amount_matches = Decimal(str(paid_amount)) == Decimal(expected_amount)
    except Exception:
        amount_matches = False
    if not amount_matches or paid_currency != "RUB":
        await db.update_payment_status(payment_row["payment_id"], "amount_mismatch")
        logger.error("YooKassa amount mismatch for payment %s", payment_row["payment_id"])
        return

    await db.update_payment_status(payment_row["payment_id"], "succeeded")
    await _fulfill(await db.get_payment(payment_row["payment_id"]), db, bot)


async def poll_payment_orders(bot, db: Database) -> None:
    """Poll pending YooKassa payments and recover grants after restarts."""
    while True:
        try:
            for payment_row in await db.get_unfinished_payments():
                try:
                    await _check_payment(payment_row, db, bot)
                except Exception:
                    logger.exception(
                        "Payment processing failed for %s", payment_row["payment_id"]
                    )
        except Exception:
            logger.exception("Could not load unfinished payments")
        await asyncio.sleep(10)
