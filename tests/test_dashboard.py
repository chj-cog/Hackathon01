import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import calc as calc_route
from app.core.config import get_settings
from app.main import app
from app.schemas.calc import CalcRequest
from app.schemas.plan import AnalysisPlan
from app.services import explain, planner
from app.services.calc import build_request
from app.services.calc.http_adapter import HttpCalculator
from app.services.calc.mock import MockCalculator
from app.services.dataset import area_ids

client = TestClient(app)
URL = "/api/dashboard/analyze"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("CALC_MODE", "mock")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_KEY", "")  # 인증은 test_security.py 에서 검증
    get_settings.cache_clear()
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


PLAN_OK = {
    "status": "ok", "intent": "region_comparison", "regions": ["성수", "홍대"],
    "metrics": [{"column": "est_sales", "op": "sum"}],
}
SINGLE = {
    "status": "ok", "intent": "sales_trend", "regions": ["홍대"],
    "metrics": [{"column": "est_sales", "op": "sum"}],
}


def fake_llms(monkeypatch, plan_payload, explain_fn):
    """planner 호출(format 있음)과 explain 호출(format 없음)을 구분해서 가짜 응답."""
    async def fake_chat(message, **kw):
        if kw.get("format") is not None:
            return "m", json.dumps(plan_payload)
        return "m", explain_fn(message)

    monkeypatch.setattr(planner.ollama, "chat", fake_chat)
    monkeypatch.setattr(explain.ollama, "chat", fake_chat)


def facts_of(message: str) -> str:
    return message.split("<facts>")[1].split("</facts>")[0]


# ---- area / sql ----
def test_area_ids():
    assert area_ids(["성수"]) == "seongsu"
    assert area_ids(["성수", "홍대"]) == "seongsu,hongdae"
    assert area_ids([]) == ""


def test_response_has_exactly_three_fields_and_mock_marked(monkeypatch):
    fake_llms(monkeypatch, SINGLE, lambda m: "홍대의 월별 추정매출 합계를 정리했습니다.")
    r = client.post(URL, json={"question": "홍대의 음식점 월별 매출을 보여줘."})
    assert r.status_code == 200
    b = r.json()
    assert set(b) == {"area", "sql", "text"}
    assert b["area"] == "hongdae" and b["sql"] == ""
    assert b["text"].startswith("[테스트용 Mock")
    assert r.headers["x-is-mock"] == "true"


def test_multi_region_area_is_comma_joined(monkeypatch):
    fake_llms(monkeypatch, PLAN_OK, lambda m: "비교 결과입니다.")
    r = client.post(URL, json={"question": "성수와 홍대의 카페 매출을 비교해줘."})
    assert r.json()["area"] == "seongsu,hongdae"


def test_sql_returned_only_when_engine_reports_executed_sql(monkeypatch):
    class SqlEngine(MockCalculator):
        async def calculate(self, req):
            res = await super().calculate(req)
            res.executed_sql = "SELECT region, SUM(est_sales) FROM t GROUP BY region"
            return res

    app.dependency_overrides[calc_route._calculator] = lambda: SqlEngine()
    fake_llms(monkeypatch, PLAN_OK, lambda m: "ok")
    r = client.post(URL, json={"question": "성수와 홍대의 카페 매출을 비교해줘."})
    assert r.json()["sql"].startswith("SELECT")


# ---- text grounding ----
def test_text_uses_only_calc_numbers_when_model_complies(monkeypatch):
    def good(m):
        line = [l for l in facts_of(m).splitlines() if l.startswith("[")][0]
        return "첫 번째 결과: " + line

    fake_llms(monkeypatch, SINGLE, good)
    r = client.post(URL, json={"question": "홍대의 음식점 월별 매출을 보여줘."})
    assert r.status_code == 200 and "추정매출 합계" in r.json()["text"]


def test_invented_number_falls_back_to_template(monkeypatch):
    calls = []

    def bad(m):
        calls.append(1)
        return "홍대 매출은 987654321원으로 성수의 3.7배입니다."

    fake_llms(monkeypatch, SINGLE, bad)
    r = client.post(URL, json={"question": "홍대의 음식점 월별 매출을 보여줘."})
    text = r.json()["text"]
    assert len(calls) == explain.MAX_ATTEMPTS  # 재시도 후 포기
    assert "987654321" not in text and "3.7" not in text
    assert "계산 결과:" in text  # 결정적 템플릿


def test_ungrounded_number_detector():
    facts = ["[성수] 추정매출 합계 1,714 (사용 행 152)", "분석 기간: 2024-01~2024-12"]
    assert explain.ungrounded_numbers("성수 매출은 1714이고 기간은 2024년입니다.", facts, 1) == []
    assert explain.ungrounded_numbers("성수 매출은 2,000입니다.", facts, 1) == ["2000"]


def test_growth_percent_and_null_formatting():
    assert explain._fmt_value("growth_rate", 0.1279, []) == "+12.79%"
    assert "기준 기간 값이 0" in explain._fmt_value("growth_rate", None, ["baseline_zero"])


# ---- clarification / errors ----
def test_clarification_returns_422_without_calc(monkeypatch):
    called = []

    class Spy(MockCalculator):
        async def calculate(self, req):
            called.append(1)
            return await super().calculate(req)

    app.dependency_overrides[calc_route._calculator] = lambda: Spy()
    fake_llms(monkeypatch, {"status": "ok", "intent": "other"}, lambda m: "x")
    r = client.post(URL, json={"question": "홍대 분석 좀"})
    d = r.json()["detail"]
    assert r.status_code == 422 and d["error"] == "needs_clarification" and not called


def test_calc_error_result_returns_502(monkeypatch):
    class ErrEngine(MockCalculator):
        async def calculate(self, req):
            return self._error(req, "NO_DATA", "조건에 맞는 데이터 없음")

    app.dependency_overrides[calc_route._calculator] = lambda: ErrEngine()
    fake_llms(monkeypatch, PLAN_OK, lambda m: "x")
    r = client.post(URL, json={"question": "성수와 홍대의 카페 매출을 비교해줘."})
    assert r.status_code == 502 and r.json()["detail"]["engine_error"]["code"] == "NO_DATA"


def test_ollama_down_during_explain_returns_503(monkeypatch):
    from app.services import ollama

    async def chat(message, **kw):
        if kw.get("format") is not None:
            return "m", json.dumps(PLAN_OK)
        raise ollama.OllamaUnavailableError("down")

    monkeypatch.setattr(planner.ollama, "chat", chat)
    monkeypatch.setattr(explain.ollama, "chat", chat)
    r = client.post(URL, json={"question": "성수와 홍대의 카페 매출을 비교해줘."})
    assert r.status_code == 503


def test_engine_timeout_and_bad_response_mapped(monkeypatch):
    def handler_timeout(request):
        raise httpx.ReadTimeout("slow")

    def make(handler):
        c = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://engine")
        return HttpCalculator("http://engine", 5, client=c)

    fake_llms(monkeypatch, PLAN_OK, lambda m: "x")
    app.dependency_overrides[calc_route._calculator] = lambda: make(handler_timeout)
    assert client.post(URL, json={"question": "성수와 홍대의 카페 매출을 비교해줘."}).status_code == 504
    app.dependency_overrides[calc_route._calculator] = lambda: make(lambda r: httpx.Response(200, json={"x": 1}))
    assert client.post(URL, json={"question": "성수와 홍대의 카페 매출을 비교해줘."}).status_code == 502


def test_real_engine_result_has_no_mock_prefix(monkeypatch):
    """실제(비 Mock) 엔진 결과면 Mock 표시가 붙지 않아야 한다."""
    class RealLike(MockCalculator):
        async def calculate(self, req):
            res = await super().calculate(req)
            res.is_mock = False
            res.data_source = "commercial_area_db"
            res.data_version = "2024-12-01"
            return res

    app.dependency_overrides[calc_route._calculator] = lambda: RealLike()
    fake_llms(monkeypatch, SINGLE, lambda m: "설명입니다.")
    r = client.post(URL, json={"question": "홍대의 음식점 월별 매출을 보여줘."})
    assert r.status_code == 200 and "x-is-mock" not in r.headers
    assert not r.json()["text"].startswith("[테스트용")


def test_existing_calc_result_accepts_executed_sql_optional():
    req = build_request(
        AnalysisPlan.model_validate(dict(
            intent="region_comparison", regions=["성수"], industries=[],
            metrics=[{"column": "est_sales", "op": "sum"}], group_by=["region"],
            comparison="region", filters=[], period=None, time_column="year_month")),
        "ds", "rid")
    assert isinstance(req, CalcRequest)


def test_ranking_judgment_words_rejected(monkeypatch):
    calls = []

    def ranked(m):
        calls.append(1)
        return "홍대가 가장 높고 창업을 추천합니다."

    fake_llms(monkeypatch, SINGLE, ranked)
    r = client.post(URL, json={"question": "홍대의 음식점 월별 매출을 보여줘."})
    assert len(calls) == explain.MAX_ATTEMPTS
    assert "추천" not in r.json()["text"] and "계산 결과:" in r.json()["text"]
    assert explain.judgment_words("가장 큰 증가율") == ["가장"]
