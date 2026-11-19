"""계산 엔진 연동 예외. status_code 는 API 응답 코드."""
from app.schemas.calc import CalcError


class CalcIntegrationError(Exception):
    status_code = 500


class CalcRequestError(CalcIntegrationError):
    """분석 계획을 계산 요청으로 변환할 수 없음."""

    status_code = 422


class CalcConfigError(CalcIntegrationError):
    status_code = 503


class CalcUnavailableError(CalcIntegrationError):
    status_code = 503


class CalcTimeoutError(CalcIntegrationError):
    status_code = 504


class CalcResponseError(CalcIntegrationError):
    """엔진 응답이 규격과 다르거나 요청과 불일치."""

    status_code = 502


class CalcEngineError(CalcIntegrationError):
    """엔진이 status=error 로 응답."""

    status_code = 502

    def __init__(self, error: CalcError):
        super().__init__(f"[{error.code}] {error.message}")
        self.error = error
