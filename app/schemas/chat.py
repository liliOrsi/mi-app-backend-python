from pydantic import BaseModel
from typing import Any, Optional


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    messages_history: list[Any] = []
    user_email: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    expense_created: Optional[dict] = None
    pending_expense: Optional[dict] = None
    pending_income: Optional[dict] = None
    pending_reminder: Optional[dict] = None
    messages_history: list[Any] = []
    history: list[HistoryMessage]
