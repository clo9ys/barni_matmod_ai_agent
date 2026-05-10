from fastapi import APIRouter
from .api import router as api

router = APIRouter()

router.include_router(api)