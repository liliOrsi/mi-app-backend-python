import json
import asyncio
from datetime import date
from typing import Any

import requests
import anthropic

from app.core.config import settings

NESTJS_BASE = getattr(settings, "NESTJS_BASE_URL", "http://localhost:3000")
MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


TOOLS = [
    {
        "name": "get_expenses",
        "description": "Obtiene la lista de gastos registrados. Se puede filtrar por rango de fechas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "to":   {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
            },
        },
    },
    {
        "name": "get_categories",
        "description": "Obtiene todas las categorías de gastos disponibles.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_totals",
        "description": "Obtiene los totales de gastos agrupados por categoría para un período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "to":   {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
            },
        },
    },
    {
        "name": "create_category",
        "description": "Crea una nueva categoría de gasto cuando ninguna de las existentes aplica. Llamá get_categories primero, y solo creá una nueva si realmente no hay ninguna apropiada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":  {"type": "string", "description": "Nombre de la categoría en español, conciso (ej: 'Supermercado', 'Salud', 'Transporte')"},
                "icon":  {"type": "string", "description": "Emoji representativo, ej: '🛒'"},
                "color": {"type": "string", "description": "Color hex ej: '#4CAF50'"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "propose_expense",
        "description": "Propone un gasto para que el usuario lo confirme. Usá SIEMPRE esta herramienta en lugar de crear directamente. El usuario verá los detalles y podrá confirmar o cancelar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description":  {"type": "string",  "description": "Descripción del gasto"},
                "amount":       {"type": "number",  "description": "Monto positivo"},
                "date":         {"type": "string",  "description": "Fecha YYYY-MM-DD"},
                "type":         {"type": "string",  "enum": ["FIXED", "VARIABLE"], "description": "FIXED para gastos mensuales recurrentes, VARIABLE para el resto"},
                "moneyType":    {"type": "string",  "enum": ["ARS", "USD"]},
                "categoryId":   {"type": "integer", "description": "ID de la categoría"},
                "categoryName": {"type": "string",  "description": "Nombre legible de la categoría para mostrar al usuario"},
                "isRecurring":  {"type": "boolean"},
                "recurringDay": {"type": "integer", "description": "Día del mes (1-31), solo para FIXED"},
                "fromAccount":  {"type": "string", "enum": ["efectivo", "banco"], "description": "Con qué cuenta se pagó. Efectivo por defecto."},
            },
            "required": ["description", "amount", "date", "type", "moneyType", "categoryId", "categoryName"],
        },
    },
]

SYSTEM_PROMPT = """\
Sos un asistente financiero personal para GastoFácil, una app de control de gastos.
Fecha de hoy: {today}

Podés consultar gastos, analizarlos y registrar nuevos gastos con lenguaje natural.

Reglas para REGISTRAR un gasto (MUY IMPORTANTE):
1. Llamá get_categories para ver las categorías disponibles.
2. Elegí la categoría más apropiada. Si ninguna aplica claramente, llamá create_category para crear una nueva con nombre, emoji e ícono adecuados, y usá el ID retornado.
3. Fecha no especificada → hoy. Moneda no especificada → ARS. Tipo no especificado → VARIABLE.
4. Llamá propose_expense con todos los datos, incluyendo fromAccount ('efectivo' si pagó en efectivo, 'banco' si fue débito/transferencia bancaria). NUNCA crees el gasto directamente.
5. Tras proponer, escribí UNA oración corta: qué se va a registrar, cuánto y en qué categoría. El usuario verá botones para confirmar o cancelar.

Reglas para CONSULTAR:
- get_expenses para listar gastos individuales.
- get_totals para resúmenes por categoría.
- Respondé de forma breve y directa. Sin listas largas salvo que el usuario las pida.

Respondé siempre en español. Sé conciso y amigable.\
"""


def _call_tool(name: str, input_data: dict) -> Any:
    try:
        if name == "get_expenses":
            params = {k: input_data[k] for k in ("from", "to") if k in input_data}
            r = requests.get(f"{NESTJS_BASE}/expenses", params=params, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "get_categories":
            r = requests.get(f"{NESTJS_BASE}/categories", timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "get_totals":
            params = {k: input_data[k] for k in ("from", "to") if k in input_data}
            r = requests.get(f"{NESTJS_BASE}/expenses/totals", params=params, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "create_category":
            r = requests.post(f"{NESTJS_BASE}/categories", json=input_data, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "propose_expense":
            # Don't create yet — just echo back so the AI can write its confirmation message
            return {"proposed": True, **input_data}

        return {"error": f"Herramienta desconocida: {name}"}

    except requests.RequestException as exc:
        return {"error": str(exc)}


def create_expense_direct(data: dict) -> dict:
    payload = {k: v for k, v in data.items() if k not in ("categoryName", "proposed")}
    r = requests.post(f"{NESTJS_BASE}/expenses", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def _serialize_content(content: Any) -> Any:
    """Convert Anthropic SDK content blocks to plain JSON-serializable dicts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if hasattr(block, "model_dump"):
                out.append(block.model_dump())
            elif isinstance(block, dict):
                out.append(block)
        return out
    if hasattr(content, "model_dump"):
        return content.model_dump()
    return content


def _serialize_messages(messages: list) -> list:
    return [{"role": m["role"], "content": _serialize_content(m["content"])} for m in messages]


async def process_chat(
    message: str,
    history: list[dict],
    messages_history: list | None = None,
) -> dict:
    today = date.today().isoformat()
    system = SYSTEM_PROMPT.format(today=today)
    client = get_client()
    pending_expense = None

    # Prefer full messages_history (preserves tool context) over text-only history
    if messages_history:
        messages: list = list(messages_history) + [{"role": "user", "content": message}]
    else:
        messages: list = list(history) + [{"role": "user", "content": message}]

    while True:
        response = await asyncio.to_thread(
            client.messages.create,
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if hasattr(b, "text")), "")
            # Append final assistant turn so next request has full context
            messages.append({"role": "assistant", "content": text})
            # Text-only history kept for simple display fallback
            new_history = list(history) + [
                {"role": "user",      "content": message},
                {"role": "assistant", "content": text},
            ]
            return {
                "response": text,
                "expense_created": None,
                "pending_expense": pending_expense,
                "messages_history": _serialize_messages(messages),
                "history": new_history,
            }

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await asyncio.to_thread(_call_tool, block.name, block.input)
                    if block.name == "propose_expense":
                        pending_expense = dict(block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return {
        "response": "No pude procesar la consulta.",
        "expense_created": None,
        "pending_expense": None,
        "messages_history": _serialize_messages(messages),
        "history": list(history) + [{"role": "user", "content": message}],
    }
