import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analyze


app = FastAPI(
    title="Smart Document Analyzer API",
    description="Upload documents/images, extract text with OCR, and summarize content.",
    version="1.0.0",
)

# CORS: use CORS_ORIGINS="https://app.example.com,http://localhost:5173" for explicit origins.
# Wildcard * cannot be combined with credentials=True (Starlette); omit env for dev-friendly *.
_cors_raw = (os.getenv("CORS_ORIGINS") or "").strip()
if _cors_raw:
    _origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(analyze.router, prefix="/api", tags=["analyze"])


@app.get("/")
def health_check() -> dict:
    return {"message": "Smart Document Analyzer API is running."}
