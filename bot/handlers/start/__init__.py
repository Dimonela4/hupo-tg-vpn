from aiogram import Router

from bot.handlers.start.registration import router as registration_router
from bot.handlers.start.referral import router as referral_router
from bot.handlers.start.navigation import router as navigation_router
from bot.handlers.start.info import router as info_router


router = Router()

router.include_router(registration_router)
router.include_router(referral_router)
router.include_router(navigation_router)
router.include_router(info_router)