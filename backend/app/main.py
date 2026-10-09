"""create_app(): nạp module đang bật (registry), middleware, chuẩn lỗi, health/readiness/metrics.

FastAPI chỉ cung cấp REST API dưới /api (không render giao diện; React SPA là build riêng).
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text

from app import registry
from app.shared.config import settings
from app.shared.db import SessionLocal
from app.shared.http import install_error_handlers
from app.shared.logging import request_id_var, setup_logging
from app.shared.security.session import redis_client

REQUESTS = Counter("http_requests_total", "Số HTTP request", ["method", "route", "status"])
LATENCY = Histogram(
    "http_request_duration_seconds", "Độ trễ HTTP", ["method", "route"], buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)
)
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin"}


def readiness() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        settings.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        probe = settings.STORAGE_ROOT / ".ready"
        probe.write_bytes(b"ok")
        probe.unlink()
        checks["storage"] = "ok"
    except OSError as exc:
        checks["storage"] = f"error: {type(exc).__name__}"
    if settings.SESSION_BACKEND == "redis":
        try:
            redis_client().ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {type(exc).__name__}"
    return checks


def create_app() -> FastAPI:
    setup_logging(settings.LOG_LEVEL)
    modules = registry.activate()
    app = FastAPI(
        title="Hệ thống số hóa hồ sơ tài liệu",
        version="0.5.0",
        description="REST API (SDD v0.5 mục 7). Session cookie + X-CSRF-Token cho thao tác ghi.",
    )

    @app.middleware("http")
    async def _context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = (request.headers.get("x-request-id") or uuid.uuid4().hex)[:64]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            route = str(getattr(request.scope.get("route"), "path", "unmatched"))
            if not request.url.path.startswith(("/metrics", "/health")):
                LATENCY.labels(request.method, route).observe(time.perf_counter() - start)
                REQUESTS.labels(request.method, route, str(status)).inc()
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    install_error_handlers(app)
    for m in modules:
        for router in m.all_routers():
            app.include_router(router)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/ready", tags=["ops"])
    def ready() -> JSONResponse:
        checks = readiness()
        ok = all(v == "ok" for v in checks.values())
        return JSONResponse({"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503)

    # HEAD cho công cụ giám sát/uptime, load balancer và wait-on (CI) - chúng mặc định gửi HEAD.
    # Route riêng, ẩn khỏi OpenAPI: một route nhiều method thì FastAPI đặt operationId theo phần tử
    # đầu của một set (thứ tự ngẫu nhiên mỗi tiến trình) -> openapi.json không ổn định.
    app.add_api_route("/health", health, methods=["HEAD"], include_in_schema=False)
    app.add_api_route("/api/health/ready", ready, methods=["HEAD"], include_in_schema=False)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
