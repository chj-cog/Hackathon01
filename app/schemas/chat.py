from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="사용자 질문")
    system: str | None = Field(None, description="선택적 시스템 프롬프트")
    model: str | None = Field(None, description="미지정 시 OLLAMA_MODEL 사용")
    temperature: float = Field(0.3, ge=0, le=2)


class ChatResponse(BaseModel):
    model: str
    reply: str
    elapsed_ms: int
    role: Literal["assistant"] = "assistant"