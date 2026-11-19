"""C 담당 계산 엔진 HTTP 어댑터. POST {CALC_ENGINE_URL}/calculate"""
import httpx
from pydantic import ValidationError

from app.schemas.calc import CalcRequest, CalcResult
from app.services.calc.errors import (
    CalcEngineError,
    CalcResponseError,
    CalcTimeoutError,
    CalcUnavailableError,
)
from app.services.calc.verify import verify_result

CALCULATE_PATH = "/calculate"


class HttpCalculator:
    def __init__(self, base_url: str, timeout: float, client: httpx.AsyncClient | None = None):
        self.base_url = base_url
        self.timeout = timeout
        self._client = client

    async def calculate(self, request: CalcRequest) -> CalcResult:
        own = self._client is None
        client = self._client or httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        try:
            resp = await client.post(CALCULATE_PATH, json=request.model_dump(mode="json"))
        except httpx.TimeoutException as e:
            raise CalcTimeoutError(f"계산 엔진 응답 시간 초과 ({self.timeout}s)") from e
        except httpx.TransportError as e:
            raise CalcUnavailableError(f"계산 엔진에 연결할 수 없습니다 ({self.base_url})") from e
        finally:
            if own:
                await client.aclose()

        try:
            result = CalcResult.model_validate(resp.json())
        except (ValueError, ValidationError) as e:
            raise CalcResponseError(
                f"계산 엔진 응답이 규격(v1.0)과 다릅니다 (HTTP {resp.status_code}): {str(e)[:200]}"
            ) from e
        if result.status == "error":  # 엔진이 보고한 오류
            verify_result(request, result)
            raise CalcEngineError(result.error)
        if resp.status_code >= 400:
            raise CalcResponseError(f"HTTP {resp.status_code} 인데 status=ok 응답입니다")
        if result.is_mock:
            raise CalcResponseError("실제 엔진 응답에 is_mock=true 가 포함되어 있습니다")
        verify_result(request, result)
        return result
