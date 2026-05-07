# Adaptia Backend

Backend de análisis ESG construido con FastAPI, LangChain, PostgreSQL y OpenAI.

## 🚀 Características

- **FastAPI**: Framework web moderno y rápido para Python
- **LangChain**: Framework para aplicaciones de IA con OpenAI Assistant API
- **PostgreSQL**: Base de datos relacional con SQLAlchemy ORM
- **Análisis ESG**: Pipeline completo de análisis ESG automatizado con IA
- **Generación de PDFs**: Creación de reportes ESG en PDF con WeasyPrint
- **Gestión de Usuarios y Organizaciones**: Sistema completo de CRUD
- **Arquitectura modular**: Estructura organizada con routers y separación de responsabilidades

## 📋 Requisitos

- Python 3.8+
- PostgreSQL
- OpenAI API Key con acceso a Assistants API
- Las dependencias están en `requirements.txt`

## ⚙️ Configuración

### 1. Variables de Entorno

Copia el archivo de ejemplo y configura tus credenciales:

```bash
cp env.example .env
```

Configura las siguientes variables en `.env`:

```env
# OpenAI Configuration
OPENAI_API_KEY=tu_openai_api_key

# Database Configuration
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/nombre_db

# Environment
ENVIRONMENT=development
```

### 2. Instalación de Dependencias

```bash
py -3.11 -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -c "import weasyprint, zstandard, langchain; print('✅ Todo OK')"
```

## 🏃‍♂️ Ejecutar el proyecto

### Opción 1: Con FastAPI CLI (Recomendado)

```bash
fastapi dev main.py
```

### Opción 2: Con Uvicorn

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Opción 3: Con Python

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará disponible en: `http://localhost:8000`

## 🌐 Endpoints de la API

### Documentación

- **GET /** - Endpoint raíz
- **GET /docs** - Documentación interactiva (Swagger UI)
- **GET /redoc** - Documentación alternativa (ReDoc)


### Análisis ESG (`/api/esg`)

- **POST /api/esg/analyze-context** - Análisis de contexto básico
- **POST /api/esg/esg-analysis** - Análisis ESG completo (JSON)
- **POST /api/esg/esg-analysis-with-pdf** - Análisis ESG con generación de PDF
- **GET /api/esg/test-pdf-from-example** - Generar PDF de prueba desde datos de ejemplo

## 📁 Estructura del proyecto

```
adaptia--backend/
├── main.py                           # Punto de entrada de la aplicación
├── requirements.txt                  # Dependencias del proyecto
├── env.example                       # Ejemplo de variables de entorno
├── README.md                         # Este archivo
│
├── app/                              # Aplicación principal
│   ├── api/                          # API endpoints
│   │   ├── router.py                 # Router principal
│   │   └── routes/                   # Rutas organizadas por módulo
│   │       └── esg.py                # Análisis ESG
│   │
│   ├── core/                         # Configuraciones core
│   │   ├── config.py                 # Settings y configuración
│   │   └── database.py               # Configuración de base de datos
│   │
│   ├── services/                     # Lógica de negocio
│   │   │
│   │   ├── langchain/                # Workflows de LangChain
│   │   │   ├── prompts.py            # Prompts para análisis ESG
│   │   │   └── workflows.py          # Workflows de análisis
│   │   │
│   │   └── pdf_generation/           # Generación de PDFs
│   │       ├── pdf.py                # Generador de PDFs
│   │       ├── filters.py            # Filtros Jinja2 personalizados
│   │       ├── example_data.json     # Datos de ejemplo
│   │       └── templates/            # Templates HTML
│   │           └── esg_analysis.html # Template del reporte ESG
│   │
│   └── utils/                        # Utilidades
│       └── json_formatter.py         # Formateador de JSON
```

## 🏗️ Arquitectura del proyecto

### Pipeline de Análisis ESG

El sistema utiliza OpenAI Assistant API con LangChain para ejecutar un pipeline de análisis ESG que incluye:

1. **Análisis de Contexto** - Recopilación de información de la organización
2. **Análisis de Impacto** - Evaluación de impactos ambientales y sociales
3. **Análisis de Materialidad** - Identificación de temas materiales
4. **Análisis de Riesgos** - Evaluación de riesgos ESG
5. **Recomendaciones** - Generación de plan de acción
6. **Generación de PDF** - Creación de reporte profesional

El pipeline ejecuta 11 prompts secuenciales con delays automáticos para optimizar el uso de la API.

### Generación de PDFs

- Utiliza **WeasyPrint** para conversión HTML a PDF
- Templates con **Jinja2** para renderizado dinámico
- Generación en memoria (sin archivos temporales)
- Diseño profesional con CSS moderno
- Incluye gráficos, tablas y visualizaciones

## 🔧 Desarrollo

### Agregar nuevos endpoints

1. Crear archivo de ruta en `app/api/routes/`
2. Definir router con FastAPI
3. Incluir en `app/api/router.py`

### Agregar nuevos modelos

1. Crear modelo SQLAlchemy en `app/models/`
2. Crear schemas Pydantic en `app/schemas/`
3. Crear servicio en `app/services/`
4. Migrar base de datos (pendiente: Alembic)

### Agregar nuevos servicios

1. Crear módulo en `app/services/`
2. Implementar lógica de negocio
3. Importar en las rutas correspondientes

## 🛠️ Stack Tecnológico

### Framework y Core

- **FastAPI** - Framework web asíncrono
- **Uvicorn** - Servidor ASGI
- **Pydantic** - Validación de datos
- **Python-dotenv** - Gestión de variables de entorno

### Base de Datos

- **PostgreSQL** - Base de datos relacional
- **SQLAlchemy** - ORM
- **psycopg2-binary** - Driver PostgreSQL

### Inteligencia Artificial

- **LangChain** - Framework de IA
- **LangChain OpenAI** - Integración con OpenAI
- **OpenAI** - API de OpenAI (GPT-4, Assistants API)

### Generación de PDFs

- **WeasyPrint** - Conversión HTML a PDF
- **Jinja2** - Motor de templates

### Utilidades

- **Pandas** - Análisis de datos
- **Requests** - Cliente HTTP

## 📚 Documentación de referencia

- **FastAPI**: https://fastapi.tiangolo.com/
- **LangChain**: https://python.langchain.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/
- **OpenAI API**: https://platform.openai.com/docs
- **WeasyPrint**: https://doc.courtbouillon.org/weasyprint/

## 🆘 Troubleshooting

### Error de conexión a PostgreSQL

- Verifica que PostgreSQL esté ejecutándose
- Confirma que `DATABASE_URL` esté correctamente configurado
- Revisa las credenciales de acceso a la base de datos

### Error de OpenAI API

- Verifica que `OPENAI_API_KEY` esté configurado
- La API key debe ser válida y tener créditos disponibles

**Nota**: Este README refleja el estado actual del proyecto. Para contribuir o reportar issues, contacta al equipo de desarrollo.
