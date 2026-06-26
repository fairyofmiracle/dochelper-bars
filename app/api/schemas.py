from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str = "web-default"
    user_label: str = ""
    escalate: bool = False


class ChatResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[str]
    needs_operator: bool
    escalated: bool
