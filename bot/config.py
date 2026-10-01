from typing import List
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    ADMIN_IDS: List[int]

    # 3x-ui
    XRAY_PANEL_URL: str
    XRAY_SUB_URL: str
    XRAY_API_KEY: str

    DATABASE_URL: str

    XRAY_INBOUND_IDS: List[int]

    # YooKassa
    YOOKASSA_SHOP_ID: int
    YOOKASSA_SECRET_KEY: str

    # Настройки ключей
    KEY_DURATION_DAYS: int

    # Цены в копейках (100 копеек = 1 рубль)
    PRICE_30_DAYS: int
    PRICE_90_DAYS: int
    PRICE_180_DAYS: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


PLANS = {
    "30d": {
        "label": "🗓 1 месяц",
        "days": 30,
        "amount_minor": settings.PRICE_30_DAYS,
        "rub": Decimal(settings.PRICE_30_DAYS) / 100,
        "description": "Защищённое соединение на 30 дней",
    },
    "90d": {
        "label": "📅 3 месяца",
        "days": 90,
        "amount_minor": settings.PRICE_90_DAYS,
        "rub": Decimal(settings.PRICE_90_DAYS) / 100,
        "description": "Защищённое соединение на 90 дней",
    },
    "180d": {
        "label": "🗃 6 месяцев",
        "days": 180,
        "amount_minor": settings.PRICE_180_DAYS,
        "rub": Decimal(settings.PRICE_180_DAYS) / 100,
        "description": "Защищённое соединение на 180 дней",
    },
}
