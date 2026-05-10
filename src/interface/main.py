from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .app.router import router

app = FastAPI(title="nsedc ai assistant api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
