from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from src.core.database import init_db
from src.interface.app.router import router
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

DIST_PATH = os.path.join(os.getcwd(), "dist")

if os.path.exists(DIST_PATH):
    # Раздаем статику (js, css)
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_PATH, "assets")), name="static")


    # Все остальные запросы отправляем на index.html
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Если это запрос к API, не трогаем его
        if full_path.startswith("api"):
            return None
        return FileResponse(os.path.join(DIST_PATH, "index.html"))
