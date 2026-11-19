"""대시보드(A) 호출용 API 키 인증. 키는 서버 환경변수 API_KEY 로만 관리한다."""
import secrets

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    s = get_settings()
    if not s.api_key:
        if s.app_env.lower() in ("production", "prod"):
            raise HTTPException(status_code=503, detail="서버에 API_KEY가 설정되지 않았습니다")
        return  # 개발 환경에서 키 미설정 시 인증 생략
    if not x_api_key or not secrets.compare_digest(x_api_key, s.api_key):
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키입니다", headers={"WWW-Authenticate": "ApiKey"})
