from .start import router as start_router
from .homyak import router as homyak_router
from .profile import router as profile_router
from .top import router as top_router
from .premium import router as premium_router
from .bonus import router as bonus_router
from .promo import router as promo_router
from .my_cards import router as my_cards_router
from .chatik import router as chatik_router
from .shop import router as shop_router
from .inventory import router as inventory_router
from .casino import router as casino_router

routers = [
    casino_router,
    inventory_router,
    shop_router,
    chatik_router,
    my_cards_router,
    promo_router,
    premium_router,
    bonus_router,
    profile_router,
    top_router,
    start_router,
    homyak_router,
]
