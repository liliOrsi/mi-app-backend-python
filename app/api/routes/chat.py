import asyncio
import logging
import traceback
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
from app.services.chat_service import (
    process_chat,
    create_expense_direct,
    create_income_direct,
    create_reminder_direct,
    analyze_bank_statement,
)

router = APIRouter()


def _extract_token(request: Request) -> str:
    return request.headers.get("authorization", "")


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    token = _extract_token(request)
    history = [{"role": m.role, "content": m.content} for m in req.history]
    try:
        result = await process_chat(
            req.message,
            history,
            req.messages_history or None,
            user_email=req.user_email or "",
            token=token,
        )
    except Exception as e:
        logger.error("Error in process_chat: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
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
async def confirm_expense(payload: dict, request: Request):
    token = _extract_token(request)
    try:
        created = await asyncio.to_thread(create_expense_direct, payload, token)
        return created
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/confirm-income")
async def confirm_income(payload: dict, request: Request):
    token = _extract_token(request)
    try:
        created = await asyncio.to_thread(create_income_direct, payload, token)
        return created
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/analyze-statement")
async def analyze_statement(
    request: Request,
    file: UploadFile = File(...),
    user_email: str = Form(""),
):
    token = _extract_token(request)
    content = await file.read()
    try:
        result = await analyze_bank_statement(
            content,
            file.filename or "statement.txt",
            token=token,
            user_email=user_email,
        )
        return result
    except Exception as exc:
        logger.error("Error analyzing statement: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/confirm-reminder")
async def confirm_reminder(payload: dict, request: Request):
    token = _extract_token(request)
    user_email = payload.pop("email", None)
    if not user_email:
        raise HTTPException(status_code=400, detail="email requerido")
    try:
        created = await asyncio.to_thread(create_reminder_direct, payload, user_email, token)
        return created
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
