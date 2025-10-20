from .start import router as start_router
from .homyak import router as homyak_router
from .profile import router as profile_router
from .top import router as top_router
from .premium import router as premium_router
from .bonus import router as bonus_router
from .promo import router as promo_router

routers = [
    promo_router,
    premium_router,
    bonus_router,
    profile_router,
    top_router,
    start_router,
    homyak_router,
]
