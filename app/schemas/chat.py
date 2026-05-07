from pydantic import BaseModel
from typing import Any, Optional


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    messages_history: list[Any] = []


class ChatResponse(BaseModel):
    response: str
    expense_created: Optional[dict] = None
    pending_expense: Optional[dict] = None
    messages_history: list[Any] = []
    history: list[HistoryMessage]
