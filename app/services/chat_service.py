import io
import json
import asyncio
import logging
from datetime import date
from typing import Any

import requests
import anthropic
import pandas as pd
from pypdf import PdfReader

from app.core.config import settings

logger = logging.getLogger(__name__)

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
    {
        "name": "get_incomes",
        "description": "Obtiene la lista de ingresos registrados. Se puede filtrar por rango de fechas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "to":   {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
            },
        },
    },
    {
        "name": "propose_income",
        "description": "Propone un ingreso para que el usuario lo confirme. Usá SIEMPRE esta herramienta en lugar de crear directamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Descripción del ingreso"},
                "amount":      {"type": "number", "description": "Monto positivo"},
                "date":        {"type": "string", "description": "Fecha YYYY-MM-DD"},
                "moneyType":   {"type": "string", "enum": ["ARS", "USD"]},
                "source":      {"type": "string", "enum": ["SALARY", "FREELANCE", "TRANSFER", "REFUND", "OTHER"], "description": "Origen del ingreso"},
                "fromAccount": {"type": "string", "enum": ["efectivo", "banco"], "description": "En qué cuenta se recibió. Banco por defecto."},
            },
            "required": ["description", "amount", "date", "moneyType", "source"],
        },
    },
    {
        "name": "propose_reminder",
        "description": "Propone un recordatorio para que el usuario lo confirme. Usá SIEMPRE esta herramienta en lugar de crear directamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description":         {"type": "string", "description": "Descripción del recordatorio"},
                "remindAt":            {"type": "string", "description": "Fecha y hora del recordatorio en formato ISO 8601, ej: '2025-06-15T10:00:00'"},
                "notifyBeforeMinutes": {"type": "integer", "description": "Minutos antes de remindAt para enviar la notificación. 0 = exactamente en remindAt. Máximo 10080 (7 días)."},
            },
            "required": ["description", "remindAt"],
        },
    },
]

SYSTEM_PROMPT = """\
Sos un asistente financiero personal para GastoFácil, una app de control de gastos.
Fecha de hoy: {today}
Email del usuario: {user_email}

Podés consultar y registrar gastos, ingresos y recordatorios con lenguaje natural.

Reglas para REGISTRAR un GASTO (MUY IMPORTANTE):
1. Llamá get_categories para ver las categorías disponibles.
2. Elegí la categoría más apropiada. Si ninguna aplica claramente, llamá create_category para crear una nueva con nombre, emoji e ícono adecuados, y usá el ID retornado.
3. Fecha no especificada → hoy. Moneda no especificada → ARS. Tipo no especificado → VARIABLE.
4. Llamá propose_expense con todos los datos, incluyendo fromAccount ('efectivo' si pagó en efectivo, 'banco' si fue débito/transferencia bancaria). NUNCA crees el gasto directamente.
5. Tras proponer, escribí UNA oración corta: qué se va a registrar, cuánto y en qué categoría. El usuario verá botones para confirmar o cancelar.

Reglas para REGISTRAR un INGRESO:
1. Fecha no especificada → hoy. Moneda no especificada → ARS. fromAccount no especificado → banco.
2. Inferí el source según el contexto: SALARY (sueldo/salario), FREELANCE (trabajo independiente/honorarios), TRANSFER (transferencia), REFUND (reembolso/devolución), OTHER (resto).
3. Llamá propose_income. NUNCA crees el ingreso directamente.
4. Tras proponer, escribí UNA oración corta con el monto y la fuente. El usuario verá botones para confirmar o cancelar.

Reglas para REGISTRAR un RECORDATORIO:
1. remindAt debe ser una fecha y hora futura en formato ISO 8601 (ej: '2025-06-15T10:00:00'). Si el usuario no indica hora, usá las 09:00.
2. notifyBeforeMinutes es opcional; si el usuario pide que le avisen antes, convertí el tiempo a minutos.
3. Llamá propose_reminder con description, remindAt y opcionalmente notifyBeforeMinutes. NUNCA crees el recordatorio directamente.
4. Tras proponer, confirmá brevemente qué se va a recordar y cuándo.

Reglas para CONSULTAR:
- get_expenses para listar gastos individuales.
- get_totals para resúmenes de gastos por categoría.
- get_incomes para listar ingresos.
- Respondé de forma breve y directa. Sin listas largas salvo que el usuario las pida.

Respondé siempre en español. Sé conciso y amigable.\
"""


def _auth_headers(token: str) -> dict:
    return {"Authorization": token} if token else {}


def _call_tool(name: str, input_data: dict, token: str = "") -> Any:
    headers = _auth_headers(token)
    logger.info("_call_tool: %s | token present: %s", name, bool(token))
    try:
        if name == "get_expenses":
            params = {k: input_data[k] for k in ("from", "to") if k in input_data}
            r = requests.get(f"{NESTJS_BASE}/expenses", params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "get_categories":
            r = requests.get(f"{NESTJS_BASE}/categories", headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "get_totals":
            params = {k: input_data[k] for k in ("from", "to") if k in input_data}
            r = requests.get(f"{NESTJS_BASE}/expenses/totals", params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "create_category":
            r = requests.post(f"{NESTJS_BASE}/categories", json=input_data, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "propose_expense":
            return {"proposed": True, **input_data}

        if name == "get_incomes":
            params = {k: input_data[k] for k in ("from", "to") if k in input_data}
            r = requests.get(f"{NESTJS_BASE}/incomes", params=params, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()

        if name == "propose_income":
            return {"proposed": True, **input_data}

        if name == "propose_reminder":
            return {"proposed": True, **input_data}

        return {"error": f"Herramienta desconocida: {name}"}

    except requests.RequestException as exc:
        logger.error("_call_tool %s failed: %s", name, exc)
        return {"error": str(exc)}


def create_expense_direct(data: dict, token: str = "") -> dict:
    payload = {k: v for k, v in data.items() if k not in ("categoryName", "proposed")}
    r = requests.post(f"{NESTJS_BASE}/expenses", json=payload, headers=_auth_headers(token), timeout=10)
    r.raise_for_status()
    return r.json()


def create_income_direct(data: dict, token: str = "") -> dict:
    payload = {k: v for k, v in data.items() if k != "proposed"}
    r = requests.post(f"{NESTJS_BASE}/incomes", json=payload, headers=_auth_headers(token), timeout=10)
    r.raise_for_status()
    return r.json()


def create_reminder_direct(data: dict, user_email: str, token: str = "") -> dict:
    payload = {k: v for k, v in data.items() if k != "proposed"}
    payload["email"] = user_email
    r = requests.post(f"{NESTJS_BASE}/reminders", json=payload, headers=_auth_headers(token), timeout=10)
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


def _extract_text_from_file(content: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "csv":
        raw = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                raw = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if raw is None:
            raw = content.decode("latin-1", errors="replace")
        first_cols = raw.strip().split("\n")[0].split(",")
        try:
            float(first_cols[2].strip())
            raw = "fecha,descripcion,debito,credito\n" + raw
        except (ValueError, IndexError):
            pass
        return raw
    if ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(content))
        return df.to_string(index=False)
    return content.decode("utf-8", errors="replace")


def _split_into_chunks(text: str, chunk_size: int = 35) -> list[str]:
    """Split statement text into chunks preserving the header row."""
    lines = [l for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return []
    # Detect header: first field of first line is non-numeric
    try:
        float(lines[0].split(",")[0].strip())
        header, data = None, lines
    except ValueError:
        header, data = lines[0], lines[1:]
    chunks = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        chunks.append((header + "\n" + "\n".join(chunk)) if header else "\n".join(chunk))
    return chunks or [text]


_STATEMENT_TOOL = {
    "name": "record_transactions",
    "description": "Registra todas las transacciones extraídas y categorizadas del resumen bancario.",
    "input_schema": {
        "type": "object",
        "properties": {
            "transactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description":          {"type": "string"},
                        "amount":               {"type": "number"},
                        "date":                 {"type": "string"},
                        "isExpense":            {"type": "boolean"},
                        "moneyType":            {"type": "string", "enum": ["ARS", "USD"]},
                        "type":                 {"type": "string", "enum": ["FIXED", "VARIABLE"]},
                        "categoryId":           {"type": ["integer", "null"], "description": "ID de la categoría de la lista. OBLIGATORIO para gastos, null solo para ingresos."},
                        "categoryName":         {"type": ["string", "null"]},
                        "fromAccount":          {"type": "string"},
                        "source":               {"type": ["string", "null"]},
                        "needsNewCategory":     {"type": "boolean"},
                        "suggestedCategoryName":  {"type": ["string", "null"]},
                        "suggestedCategoryIcon":  {"type": ["string", "null"]},
                        "suggestedCategoryColor": {"type": ["string", "null"]},
                    },
                    "required": ["description", "amount", "date", "isExpense", "moneyType",
                                 "type", "fromAccount", "needsNewCategory"],
                },
            }
        },
        "required": ["transactions"],
    },
}


async def analyze_bank_statement(
    file_content: bytes,
    filename: str,
    token: str = "",
    user_email: str = "",
) -> dict:
    today = date.today().isoformat()
    client = get_client()

    statement_text = _extract_text_from_file(file_content, filename)
    categories = await asyncio.to_thread(_call_tool, "get_categories", {}, token)
    categories_str = json.dumps(categories, ensure_ascii=False, indent=2)

    prompt = f"""Analizá el siguiente fragmento de resumen de cuenta bancaria y extraé TODAS las transacciones. Luego llamá a la herramienta record_transactions con los datos.

Fecha de hoy: {today}

Formato: columnas "debito" y "credito". debito > 0 = GASTO, credito > 0 = INGRESO. Ignorá filas donde ambos sean 0.

Reglas de categorización:
1. Usá tu conocimiento general para identificar cada comercio.
2. Comercios conocidos (Mendoza, Argentina):
   - "YPF", "SHELL", "AXION", "OPESSA" → Combustible/Nafta
   - "JUMBO", "DIA", "CARREFOUR", "COTO", "DISCO", "WALMART", "GRANJA" → Supermercado/Almacén
   - "NETFLIX", "SPOTIFY", "DISNEY", "HBO", "AMAZON" → Entretenimiento/Streaming
   - "FARMACITY", "FARMAFAGMA", "FARMA", "farmacia", "droguería" → Salud/Farmacia
   - "PEDIDOSYA", "RAPPI", "BRULEE", "ISOLINA", "LA PARRA", "pizz", "cafe", "JEBBS" → Restaurante/Delivery
   - "EDEMSA" → Electricidad (distribuidora de luz de Mendoza)
   - "ECOGAS", "ECOGAS CUYANA" → Gas (distribuidora de gas de Mendoza)
   - "MOVISTAR", "CLARO", "PERSONAL", "FIBERTEL" → Telefonía/Internet
   - "PAGO VISA", "PAGO MASTERCARD" → Tarjetas de crédito
   - "HIPERMASCOTAS", "CL HIPERMASCOTAS", "veterinaria", "mascotas" → Mascotas
   - "CENTRO MEDICO", "medico", "clinica", "hospital", "salud" → Salud/Médico
   - "PAGO SEG", "SEGURO DE VIDA", "SEGURO HOGAR" → Seguros
   - "MERPAGO", "MERCADOPAGO" + nombre → identificá por el nombre del receptor (ej: "MERPAGO BRULEE" → restaurante, "MERPAGO AA2000" → estacionamiento)
   - "SINCRONIA", "SINERGIA", "DINAMICA", "LPQ", "LUJAN AGRICOLA", "PLASTICOS", "WEISS", "VIRGEN DEL VALLE", "MODESTO ALVEAR" → usá tu criterio por el nombre para asignar la categoría más lógica
3. La categoría "Bancos" es SOLO para: mantenimiento de cuenta, intereses, impuestos bancarios (IMP S/DEBITOS, IMP S/CRED, SELLADO, PERCEPCION IVA, MANTENIMIENTO DE CUENTA, EXTRACTO, PAQUETE GESTION, DEBITO LIQUIDACION).
   NO pongas en Bancos: pagos de servicios, compras en comercios, transferencias a terceros.
4. Si el comercio no tiene categoría apropiada en la lista → needsNewCategory: true, categoryId: null, y sugerí un nombre claro (ej: "Electricidad", "Gas", "Mascotas", "Telefonía"), un emoji representativo y un color hex.
5. "DEBITO INMEDIATO" y "TRANSF" sin destino claro → categoría más cercana disponible o nueva categoría "Transferencias".
6. Para INGRESOS (credito > 0): isExpense=false, categoryId=null, source=SALARY|FREELANCE|TRANSFER|REFUND|OTHER.
7. Moneda ARS por defecto. fromAccount siempre "banco".
8. type "FIXED" para servicios recurrentes (luz, gas, teléfono, seguros), "VARIABLE" para el resto.
9. Fechas en formato MM/DD/AA → convertí a YYYY-MM-DD.

Categorías disponibles:
{categories_str}

Movimientos a analizar:
{{STATEMENT_TEXT}}"""

    chunks = _split_into_chunks(statement_text)
    print(f"[STATEMENT] {len(statement_text)} chars → {len(chunks)} chunks", flush=True)

    tools = [_STATEMENT_TOOL]
    all_transactions: list = []

    for idx, chunk in enumerate(chunks):
        if idx > 0:
            await asyncio.sleep(5)

        messages = [{"role": "user", "content": prompt.replace("{STATEMENT_TEXT}", chunk)}]

        while True:
            for attempt in range(4):
                try:
                    response = await asyncio.to_thread(
                        client.messages.create,
                        model=MODEL,
                        max_tokens=8096,
                        tools=tools,
                        messages=messages,
                    )
                    break
                except anthropic.RateLimitError:
                    wait = 30 * (attempt + 1)
                    print(f"[STATEMENT] rate limit, waiting {wait}s (attempt {attempt+1})", flush=True)
                    await asyncio.sleep(wait)
            else:
                print("[STATEMENT] giving up on chunk after retries", flush=True)
                break
            print(f"[STATEMENT] chunk {idx+1}/{len(chunks)} stop_reason={response.stop_reason}", flush=True)

            if response.stop_reason == "end_turn":
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if not hasattr(block, "type"):
                    continue
                if block.type == "tool_use" and block.name == "record_transactions":
                    txs = block.input.get("transactions", [])
                    print(f"[STATEMENT] chunk {idx+1}: {len(txs)} transactions", flush=True)
                    all_transactions.extend(txs)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": "ok"})

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break

    print(f"[STATEMENT] total: {len(all_transactions)} transactions", flush=True)
    return {"transactions": all_transactions}




async def process_chat(
    message: str,
    history: list[dict],
    messages_history: list | None = None,
    user_email: str = "",
    token: str = "",
) -> dict:
    today = date.today().isoformat()
    system = SYSTEM_PROMPT.format(today=today, user_email=user_email or "no especificado")
    client = get_client()
    pending_expense = None
    pending_income = None
    pending_reminder = None

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
                "pending_income": pending_income,
                "pending_reminder": pending_reminder,
                "messages_history": _serialize_messages(messages),
                "history": new_history,
            }

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await asyncio.to_thread(_call_tool, block.name, block.input, token)
                    if block.name == "propose_expense":
                        pending_expense = dict(block.input)
                    elif block.name == "propose_income":
                        pending_income = dict(block.input)
                    elif block.name == "propose_reminder":
                        pending_reminder = dict(block.input)
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
        "pending_income": None,
        "pending_reminder": None,
        "messages_history": _serialize_messages(messages),
        "history": list(history) + [{"role": "user", "content": message}],
    }
