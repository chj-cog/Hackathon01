from fastapi import APIRouter

from app.api.routes import calc, chat, dashboard, health, plan

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router, prefix="/api")
api_router.include_router(plan.router, prefix="/api")
api_router.include_router(calc.router, prefix="/api")
api_router.include_router(dashboard.router, prefix="/api")
# 이후: 보고서 생성 등
