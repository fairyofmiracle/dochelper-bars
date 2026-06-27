from pydantic import BaseModel, Field


class SourceSnippetOut(BaseModel):
    source: str
    excerpt: str
    chunk_index: int
    score: float
    download_url: str


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
    images: list[str] = []
    source_snippets: list[SourceSnippetOut] = []
    user_question: str = ""
    image_type: str = ""
    image_preview: str = ""


class OperatorReplyRequest(BaseModel):
    session_id: str
    message: str = Field(default="", max_length=4000)
    resolve: bool = False
