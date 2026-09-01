import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.db import Base, SessionLocal, engine
from app.seed import seed_data
from app.services.inventory_service import DomainError
from app.stitching.routes import router as stitching_router
from app.stitching.service import seed_garment_definitions

logger = logging.getLogger("boutiqueos")


def _error_payload(code: str, message: str, details: dict | None = None, request_id: str | None = None) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    if request_id is not None:
        payload["request_id"] = request_id
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s %(message)s",
        force=True,
    )
    logger.info(
        "application.startup",
        extra={
            "merchant_id": 1,
            "app_name": settings.app_name,
            "environment": settings.environment,
            "database_url": settings.database_url,
        },
    )
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
        seed_garment_definitions(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        request_id = getattr(request.state, "request_id", None)
        payload = _error_payload(exc.code or "DOMAIN_ERROR", exc.detail, getattr(exc, "details", None), request_id)
        return JSONResponse(status_code=exc.status_code, content=payload, headers={"X-Request-ID": request_id} if request_id else None)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        request_id = getattr(request.state, "request_id", None)
        if isinstance(detail, dict):
            code = str(detail.get("code", "HTTP_ERROR")).upper()
            message = str(detail.get("message", exc.detail))
            details = detail.get("details", {})
        else:
            if exc.status_code == 404:
                code = "RESOURCE_NOT_FOUND"
            elif exc.status_code == 409:
                code = "INVENTORY_CONFLICT"
            elif exc.status_code == 400:
                code = "INVALID_INPUT"
            elif exc.status_code == 422:
                code = "INVALID_INPUT"
            else:
                code = "HTTP_ERROR"
            message = str(detail)
            details = {}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code, message, details, request_id),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("application.unexpected_error", extra={"error_type": type(exc).__name__, "request_id": request_id})
        return JSONResponse(
            status_code=500,
            content=_error_payload("INTERNAL_ERROR", "An unexpected error occurred. Please try again.", {}, request_id),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    app.include_router(router)
    app.include_router(stitching_router)
    return app


app = create_app()
