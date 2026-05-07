import asyncio
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import process_chat, create_expense_direct

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    result = await process_chat(req.message, history, req.messages_history or None)
    return ChatResponse(
        response=result["response"],
        expense_created=result.get("expense_created"),
        pending_expense=result.get("pending_expense"),
        messages_history=result.get("messages_history", []),
        history=[{"role": m["role"], "content": m["content"]} for m in result["history"]],
    )


@router.post("/confirm")
async def confirm_expense(payload: dict):
    try:
        created = await asyncio.to_thread(create_expense_direct, payload)
        return created
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
