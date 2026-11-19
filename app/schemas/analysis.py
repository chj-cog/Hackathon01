"""Request/response models for commercial-area analysis (skeleton; refine later)."""
from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    region: str = Field(..., description="분석 대상 지역 (예: 서울 마포구 연남동)")
    business_type: str = Field(..., description="업종 (예: 카페)")
    radius_m: int = Field(500, ge=50, le=5000, description="분석 반경(m)")
    question: str | None = Field(None, description="추가 질의")


class AnalysisMetrics(BaseModel):
    """C 담당 계산 엔진 결과가 들어갈 자리."""
    metrics: dict[str, float] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    region: str
    business_type: str
    summary: str
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    model: str | None = None


class ErrorResponse(BaseModel):
    detail: str