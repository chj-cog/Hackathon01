from app.core.config import get_settings
from app.services.calc.errors import CalcConfigError
from app.services.calc.http_adapter import HttpCalculator
from app.services.calc.interface import Calculator
from app.services.calc.mock import MockCalculator

MOCK_WARNING = "테스트용 Mock 결과입니다. 실제 분석 결과가 아닙니다."


def get_calculator() -> Calculator:
    s = get_settings()
    if s.calc_mode == "mock":
        if s.app_env.lower() in ("production", "prod"):
            raise CalcConfigError("production 환경에서는 CALC_MODE=mock 을 사용할 수 없습니다")
        return MockCalculator()
    if s.calc_mode == "http":
        return HttpCalculator(s.calc_engine_url, s.calc_timeout_seconds)
    raise CalcConfigError(f"알 수 없는 CALC_MODE: {s.calc_mode}")
