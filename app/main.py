from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Is-Mock", "X-Data-Source"],  # 대시보드가 Mock 표시를 읽을 수 있게
    )
    app.include_router(api_router)
    return app


app = create_app()