"""FastAPI application factory for the ABC Security Camera Optimizer."""

from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from camera_optimizer.api.router import router


def _sanitize_error_element(val: Any) -> Any:
    """Recursively sanitize float infinity, NaN, and Exception objects in validation errors.

    Ensures that RequestValidationError responses can always be serialized to compliant JSON
    without triggering ValueError or TypeError during json.dumps.
    """
    if isinstance(val, Exception):
        return str(val)
    if isinstance(val, float) and not math.isfinite(val):
        return str(val)
    if isinstance(val, dict):
        return {k: _sanitize_error_element(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_error_element(v) for v in val]
    return val


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    app = FastAPI(
        title="ABC Security Camera Optimizer API",
        description=(
            "Backend API integrating the strictly sequential Artificial Bee Colony (ABC) optimizer "
            "for automated 2D security camera deployment and optical coverage simulation."
        ),
        version="0.4.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for local development and future React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle request validation errors, sanitizing non-finite floats safely."""
        sanitized = [_sanitize_error_element(err) for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": sanitized},
        )

    # Mount API router
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "ABC Security Camera Optimizer API",
            "version": "0.4.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
