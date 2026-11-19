import time

from fastapi import APIRouter, HTTPException

from app.schemas.plan import PlanRequest, PlanResponse
from app.services import ollama, planner

router = APIRouter(tags=["plan"])


@router.post("/plan", response_model=PlanResponse)
async def create_plan(req: PlanRequest) -> PlanResponse:
    """자연어 질문 -> 구조화 분석 계획 (계산 실행 없음)."""
    start = time.perf_counter()
    try:
        _, resp = await planner.make_plan(req.question, req.dataset)
    except ollama.OllamaError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except planner.PlanOutputError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except planner.PlanValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "plan_validation_failed", "violations": e.violations},
        ) from e
    resp.elapsed_ms = int((time.perf_counter() - start) * 1000)
    return resp