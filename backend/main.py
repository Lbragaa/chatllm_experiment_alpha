from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from backend.database import engine
from backend.migrations import initialize_database
from backend.routers.auth import router as auth_router
from backend.routers.chat import router as chat_router
from backend.routers.sessions import router as sessions_router

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers.update(NO_CACHE_HEADERS)
        return response


def create_app(database_engine=None):
    database_engine = database_engine if database_engine is not None else engine

    @asynccontextmanager
    async def lifespan(application):
        initialize_database(database_engine)
        yield

    application = FastAPI(title="ChatLLM Experiment API", lifespan=lifespan)
    application.state.session_factory = sessionmaker(bind=database_engine, autoflush=False)
    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"],
    )
    application.add_middleware(NoCacheMiddleware)
    application.include_router(auth_router)
    application.include_router(sessions_router)
    application.include_router(chat_router)
    if FRONTEND_DIR.exists():
        application.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

    @application.get("/")
    def root():
        index_path = FRONTEND_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="frontend/index.html nao encontrado")
        return FileResponse(index_path, headers=NO_CACHE_HEADERS)

    return application


# Importing the application never creates or alters a database.
app = create_app()
