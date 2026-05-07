from fastapi import FastAPI
from app.api.router import api_router
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Adaptia API")

app.include_router(api_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Adaptia API"}

print("🚀 Python API iniciada en puerto:", os.getenv("PORT", "default"))


# ✅ Nuevo endpoint de healthcheck
@app.get("/health")
async def health():
    return {"status": "ok", "port": os.getenv("PORT", "8000")}
