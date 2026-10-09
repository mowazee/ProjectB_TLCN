"""Cấu hình test. SQLite tạm (WAL) mặc định; TEST_DATABASE_URL để chạy trên PostgreSQL.
Session dùng RedisSessionStore thật trên fakeredis; TEST_REDIS_URL (vd. redis://127.0.0.1:6379/15) để chạy
trên Redis thật - DB đó bị FLUSHDB mỗi test, đừng trỏ vào Redis đang dùng. Không cần Celery: job chạy trực tiếp."""

import io
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="docso-test-"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ["STORAGE_ROOT"] = str(_TMP / "storage")
os.environ["SESSION_BACKEND"] = "redis"
os.environ["FEATURES_ENABLED"] = ""
os.environ["LOG_LEVEL"] = "WARNING"
# NFR-09: CI chạy lại bộ test MVP với cờ P2 bật (TEST_FEATURES=workflow,... hoặc "all")
_ALL = "workflow,highlight,handwriting,extraction,classification,versions,borrowing,notifications,imports,rollback"
TEST_FEATURES = os.environ.get("TEST_FEATURES", "").replace("all", _ALL)

import fakeredis  # noqa: E402
import pymupdf  # noqa: E402
import pytest  # noqa: E402
import redis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app import registry  # noqa: E402
from app.modules.categories.application.manage import create_category  # noqa: E402
from app.modules.jobs.infrastructure import dispatcher  # noqa: E402
from app.modules.ocr.application import engines  # noqa: E402
from app.modules.ocr.domain.ports import OcrLine, OcrOutput  # noqa: E402
from app.modules.users.application.manage import create_department, create_user, seed_reference_data  # noqa: E402
from app.shared.config import settings  # noqa: E402
from app.shared.context import RequestContext  # noqa: E402
from app.shared.db import Base, SessionLocal, engine  # noqa: E402
from app.shared.security.session import get_session_store  # noqa: E402

_REAL_REDIS = redis.Redis.from_url(os.environ["TEST_REDIS_URL"]) if os.environ.get("TEST_REDIS_URL") else None

PASSWORD = "Password123!"
CTX = RequestContext(ip_address="127.0.0.1", user_agent="pytest")
FONT = next(
    (f for f in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if Path(f).exists()),
    None,
)


# ---------------------------------------------------------------- dữ liệu mẫu tự sinh
def make_pdf(lines: list[str], pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for p in range(pages):
        page = doc.new_page()
        if FONT:
            page.insert_font(fontname="vn", fontfile=FONT)
        y = 72
        for line in lines:
            page.insert_text((72, y), f"{line} (trang {p + 1})", fontname="vn" if FONT else "helv", fontsize=12)
            y += 20
    return bytes(doc.tobytes())


def make_png(text: str = "Hợp đồng số 123", size: tuple[int, int] = (600, 200)) -> bytes:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 32) if FONT else ImageFont.load_default()
    draw.text((20, 60), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FakeEngine:
    name, version = "fake", "1.0"

    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None
        self.lines = [
            OcrLine("Hop dong so 123/2026", 0.97, (20, 20, 300, 30)),
            OcrLine("Cong ty TNHH ABC", 0.70, (20, 60, 250, 30)),
        ]

    def recognize(self, image_bgr: object) -> OcrOutput:
        self.calls += 1
        if self.error:
            raise self.error
        return OcrOutput(self.name, self.version, list(self.lines))


# ---------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    if _REAL_REDIS is not None:
        _REAL_REDIS.flushdb()
    client = _REAL_REDIS if _REAL_REDIS is not None else fakeredis.FakeRedis()
    monkeypatch.setattr(redis.Redis, "from_url", classmethod(lambda cls, *a, **k: client))
    get_session_store.cache_clear()
    monkeypatch.setattr(settings, "FEATURES_ENABLED", TEST_FEATURES)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    registry.activate()
    engines.clear_instances()
    yield
    get_session_store.cache_clear()


@pytest.fixture(autouse=True)
def enqueued(monkeypatch):
    sent: list = []
    monkeypatch.setattr(dispatcher, "send", lambda job_id, queue, **_: sent.append((job_id, queue)))
    return sent


@pytest.fixture
def fake_engine():
    eng = FakeEngine()
    engines.override("print", eng)
    return eng


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def seed(db):
    seed_reference_data(db)
    admin = create_user(
        db,
        None,
        username="admin",
        email="admin@test.vn",
        full_name="Quản trị",
        password=PASSWORD,
        roles=["ADMIN"],
        ctx=CTX,
    )
    from app.shared.context import Principal

    admin_p = Principal(admin.id, "admin", "Quản trị", None, frozenset({"ADMIN"}))
    dep_a = create_department(db, admin_p, code="A", name="Phòng A", ctx=CTX)
    dep_b = create_department(db, admin_p, code="B", name="Phòng B", ctx=CTX)

    def mk(username: str, role: str, dep: int) -> object:
        return create_user(
            db,
            admin_p,
            username=username,
            email=f"{username}@test.vn",
            full_name=username.title(),
            password=PASSWORD,
            roles=[role],
            department_id=dep,
            ctx=CTX,
        )

    data = {
        "admin": admin,
        "admin_p": admin_p,
        "dep_a": dep_a,
        "dep_b": dep_b,
        "officer": mk("officer", "OFFICER", dep_a.id),
        "officer_b": mk("officerb", "OFFICER", dep_b.id),
        "approver": mk("approver", "APPROVER", dep_a.id),
    }
    data["category"] = create_category(db, admin_p, {"name": "Hợp đồng", "code": "HOP-DONG"}, CTX)
    data["category2"] = create_category(db, admin_p, {"name": "Công văn", "code": "CONG-VAN"}, CTX)
    return data


@pytest.fixture
def make_app():
    """Tạo app với tổ hợp cờ P2 cho trước (NFR-09: test MVP với cờ bật/tắt)."""
    from app.main import create_app

    def _make(features: str = "") -> object:
        settings.FEATURES_ENABLED = features
        return create_app()

    return _make


@pytest.fixture
def login(make_app):
    app_cache: dict[str, object] = {}

    def _login(username: str, password: str = PASSWORD, features: str | None = None) -> TestClient:
        key = features if features is not None else settings.FEATURES_ENABLED
        if key not in app_cache:
            app_cache[key] = make_app(key)
        client = TestClient(app_cache[key])
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        client.headers["X-CSRF-Token"] = resp.json()["csrf_token"]
        return client

    return _login


def upload(client: TestClient, category_id: int, data: bytes, filename: str, title: str | None = None, **extra):
    form = {"category_id": str(category_id), **{k: str(v) for k, v in extra.items()}}
    if title:
        form["title"] = title
    return client.post("/api/documents", data=form, files={"file": (filename, data, "application/octet-stream")})


P2_ALL = _ALL


def run_all_jobs(enqueued: list) -> list:
    from app.modules.jobs.application.runner import run_job

    outcomes = []
    while enqueued:
        job_id, _ = enqueued.pop(0)
        outcomes.append(run_job(job_id))
    return outcomes
