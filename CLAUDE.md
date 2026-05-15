# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup

```powershell
py -3.11 -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Run dev server

```powershell
fastapi dev main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`, Swagger docs at `/docs`.

### Environment variables

Copy `env.example` to `.env` and configure:

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DATABASE_URL=postgresql://...
SUPABASE_URL=
SUPABASE_ANON_KEY=
NESTJS_BASE_URL=http://localhost:3000
TAVILY_API_KEY=
```

## Architecture

This is a FastAPI backend for **GastoFácil**, a personal finance app. It acts as an AI middleware layer between the frontend and the main NestJS backend.

### Request flow

```
Frontend → Python (FastAPI) → Anthropic Claude API (tool use)
                           → NestJS backend (REST calls to /expenses, /categories)
```

The Python service does **not** own the database directly — all data mutations go through the NestJS backend at `NESTJS_BASE_URL` (default `http://localhost:3000`).

### Chat pipeline (`app/services/chat_service.py`)

The core of the app is an agentic loop in `process_chat`:

1. User message + full `messages_history` (preserves tool call context across turns) is sent to `claude-sonnet-4-6`.
2. Claude decides to call one of 5 tools: `get_expenses`, `get_categories`, `get_totals`, `create_category`, `propose_expense`.
3. `_call_tool` executes the tool by calling the NestJS REST API.
4. `propose_expense` is special: it does **not** create anything — it echoes data back to Claude so it can write a confirmation message. The pending expense is returned to the frontend.
5. The user confirms via `POST /api/chat/confirm`, which calls `create_expense_direct` to actually POST to NestJS.
6. Loop continues until `stop_reason == "end_turn"`.

Two history formats are maintained in parallel:
- `messages_history`: full Anthropic SDK message objects (includes tool call/result blocks) — used for continued agentic context.
- `history`: plain `{role, content}` text pairs — lightweight fallback for display.

### Voice routes (`app/api/routes/voice.py`)

- `POST /api/voice/tts` — text → MP3 via OpenAI `tts-1`, streamed back.
- `POST /api/voice/stt` — audio file → text via OpenAI `whisper-1` (Spanish, `language="es"`).

Both use a lazy-initialized singleton `OpenAI` client. Blocking SDK calls are wrapped in `asyncio.to_thread`.

### Router structure

```
main.py
└── app/api/router.py        ← all routes prefixed /api
    └── /chat                ← chat.py
        POST /api/chat       ← main agentic turn
        POST /api/chat/confirm
    (voice router not yet wired into api_router)
```

`app/services/langchain/` exists but is currently empty stubs — LangChain is in `requirements.txt` but the active AI path uses the Anthropic SDK directly.

### Settings

`app/core/config.py` uses `pydantic-settings` (`BaseSettings`) and reads from `.env` automatically. Import via `from app.core.config import settings`.
