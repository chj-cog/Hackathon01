"""계산기 인터페이스. 실제 계산은 C 담당 엔진(HttpCalculator 경유)에서만 수행."""
from typing import Protocol

from app.schemas.calc import CalcRequest, CalcResult


class Calculator(Protocol):
    async def calculate(self, request: CalcRequest) -> CalcResult: ...
