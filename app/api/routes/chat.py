import asyncio
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import (
    process_chat,
    create_expense_direct,
    create_income_direct,
    create_reminder_direct,
)

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    result = await process_chat(
        req.message,
        history,
        req.messages_history or None,
        user_email=req.user_email or "",
    )
    return ChatResponse(
        response=result["response"],
        expense_created=result.get("expense_created"),
        pending_expense=result.get("pending_expense"),
        pending_income=result.get("pending_income"),
        pending_reminder=result.get("pending_reminder"),
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


@router.post("/confirm-income")
async def confirm_income(payload: dict):
    try:
        created = await asyncio.to_thread(create_income_direct, payload)
        return created
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/confirm-reminder")
async def confirm_reminder(payload: dict):
    user_email = payload.pop("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="email requerido")
    try:
        created = await asyncio.to_thread(create_reminder_direct, payload, user_email)
        return created
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
