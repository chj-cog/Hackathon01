"""A 담당 대시보드용 응답 모델. 필드는 합의된 3개만 사용한다."""
from pydantic import BaseModel, Field


class DashboardRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class DashboardResponse(BaseModel):
    area: str = Field(..., description="지역 식별값 (예: seongsu). 복수 지역/미지정은 docs/DASHBOARD_API.md 참고")
    sql: str = Field("", description="실제 실행된 SQL이 있을 때만. Pandas 계산이면 빈 문자열")
    text: str = Field(..., description="계산 결과에 존재하는 수치만 사용한 설명")
