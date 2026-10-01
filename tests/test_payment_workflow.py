import os
import unittest
from unittest.mock import AsyncMock

for name, value in {
    "BOT_TOKEN": "123456:test-token",
    "ADMIN_IDS": "[]",
    "XRAY_PANEL_URL": "http://127.0.0.1:2053",
    "XRAY_SUB_URL": "https://sub.example",
    "XRAY_API_KEY": "test-api-token",
    "DATABASE_URL": "postgresql://test:test@localhost/test",
    "XRAY_INBOUND_IDS": "[1]",
    "YOOKASSA_SHOP_ID": "1",
    "YOOKASSA_SECRET_KEY": "test-secret",
    "KEY_DURATION_DAYS": "30",
    "PRICE_30_DAYS": "12000",
    "PRICE_90_DAYS": "25000",
    "PRICE_180_DAYS": "40000",
}.items():
    os.environ.setdefault(name, value)

from bot import yookassa_payment
from bot.config import PLANS, settings
from bot.services.xray import XRayService


class PaymentRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_payment_is_granted_and_notified_once(self):
        plan_id = "30d"
        row = {
            "payment_id": "payment-test",
            "tg_id": 42,
            "plan_id": plan_id,
            "amount_minor": PLANS[plan_id]["amount_minor"],
            "status": "succeeded",
            "grant_expiry_ms": None,
            "fulfilled_at": None,
            "notified_at": None,
        }

        class FakeDatabase:
            async def get_payment(self, payment_id):
                return dict(row)

            async def set_payment_grant_expiry(self, payment_id, expiry):
                row["grant_expiry_ms"] = expiry
                return expiry

            async def mark_payment_fulfilled(self, payment_id):
                row["fulfilled_at"] = True

            async def mark_payment_notified(self, payment_id):
                row["notified_at"] = True

        class FakeXRay:
            set_expiry = AsyncMock()
            get_user_key = AsyncMock(return_value="https://sub.example/key")

            async def get_expiry_date(self, user_id):
                return None

            @staticmethod
            def calculate_date(days, time_before=0):
                return 2_000_000_000_000 + days * 86_400_000

            @staticmethod
            def calculate_date_beauty(expiry_ms):
                return "01.01.2035"

        fake_xray = FakeXRay()
        original_xray = yookassa_payment.xray_service
        yookassa_payment.xray_service = fake_xray
        try:
            db = FakeDatabase()

            class FakeBot:
                send_message = AsyncMock()

            bot = FakeBot()
            await yookassa_payment._fulfill(dict(row), db, bot)
            await yookassa_payment._fulfill(dict(row), db, bot)

            fake_xray.set_expiry.assert_awaited_once_with(42, row["grant_expiry_ms"])
            bot.send_message.assert_awaited_once()
            self.assertTrue(row["fulfilled_at"])
            self.assertTrue(row["notified_at"])
        finally:
            yookassa_payment.xray_service = original_xray


class PanelClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_client_uses_configured_inbounds_and_expiry(self):
        service = XRayService()
        service._request = AsyncMock(return_value={"success": True})

        await service.create_client(30, 42, expiry_ms=2_000_000_000_000)

        service._request.assert_awaited_once()
        args, kwargs = service._request.await_args
        self.assertEqual(args[:2], ("POST", "/panel/api/clients/add"))
        self.assertEqual(kwargs["json"]["inboundIds"], settings.XRAY_INBOUND_IDS)
        self.assertEqual(kwargs["json"]["client"]["expiryTime"], 2_000_000_000_000)
        self.assertEqual(kwargs["json"]["client"]["tgId"], 42)


if __name__ == "__main__":
    unittest.main()
