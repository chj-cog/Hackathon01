"""Ollama 로컬 API 호출 모듈."""
import httpx

from app.core.config import get_settings


class OllamaError(Exception):
    status_code = 500


class OllamaUnavailableError(OllamaError):
    status_code = 503


class OllamaTimeoutError(OllamaError):
    status_code = 504


class OllamaModelNotFoundError(OllamaError):
    status_code = 404


async def chat(
    message: str,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    format: dict | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, str]:
    """Ollama /api/chat 호출. (model, reply) 반환."""
    s = get_settings()
    model = model or s.ollama_model
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if format is not None:  # Structured Outputs (JSON Schema)
        payload["format"] = format
    own = client is None
    client = client or httpx.AsyncClient(
        base_url=s.ollama_base_url, timeout=s.ollama_timeout_seconds
    )
    try:
        resp = await client.post("/api/chat", json=payload)
    except httpx.TimeoutException as e:
        raise OllamaTimeoutError(
            f"Ollama 응답 시간 초과 ({s.ollama_timeout_seconds}s)"
        ) from e
    except httpx.TransportError as e:
        raise OllamaUnavailableError(
            f"Ollama 서버에 연결할 수 없습니다 ({s.ollama_base_url}). 'ollama serve' 실행 여부를 확인하세요."
        ) from e
    finally:
        if own:
            await client.aclose()

    if resp.status_code == 404:
        raise OllamaModelNotFoundError(
            f"모델 '{model}'을(를) 찾을 수 없습니다. 'ollama pull {model}' 로 설치하세요."
        )
    if resp.status_code >= 400:
        raise OllamaError(f"Ollama 오류 {resp.status_code}: {resp.text[:200]}")
    try:
        reply = resp.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as e:
        raise OllamaError("Ollama 응답 형식이 올바르지 않습니다.") from e
    return model, reply