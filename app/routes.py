
from fastapi import APIRouter

from app.routers.public import router as public_router
from app.routers.admin import router as admin_router
from app.routers.placements import router as placements_router

router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)
router.include_router(placements_router)
