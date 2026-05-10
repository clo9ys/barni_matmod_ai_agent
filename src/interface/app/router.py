from fastapi import APIRouter
from .research import router as research
from .auth import router as auth

router = APIRouter(prefix="/api/v1")

router.include_router(research)
router.include_router(auth)