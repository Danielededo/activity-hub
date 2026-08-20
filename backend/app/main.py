"""FastAPI application entrypoint."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import analysis, health, upload, users, workouts
from app.services.parsers import ParserError

app = FastAPI(
    title="Activity Hub API",
    description="Self-hosted fitness aggregator: upload TCX/GPX files and query your training.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, users, workouts, upload, analysis):
    app.include_router(module.router, prefix=settings.api_prefix)


@app.exception_handler(ParserError)
async def parser_error_handler(_: Request, exc: ParserError) -> JSONResponse:
    """A file we cannot read is a client error, not a 500."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)}
    )


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": "Activity Hub API", "docs": "/docs", "api": settings.api_prefix}
