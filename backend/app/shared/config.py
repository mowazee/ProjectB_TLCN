"""Settings đọc từ biến môi trường / .env (Đặc tả đề tài v0.5 mục 4.10).

FEATURES_ENABLED là một nguồn sự thật cho cả backend (module nào được nạp) và React
(GET /api/auth/me trả danh sách features).
"""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

ALL_FEATURES = (
    "workflow",
    "highlight",
    "handwriting",
    "extraction",
    "classification",
    "versions",
    "borrowing",
    "notifications",
    "imports",
    "rollback",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"  # development | test | staging | production
    LOG_LEVEL: str = "INFO"
    APP_TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # Cờ tính năng P2 (để trống = chỉ MVP)
    FEATURES_ENABLED: str = ""

    # Dữ liệu
    DATABASE_URL: str = "postgresql+psycopg://dms:dms_password@localhost:5432/dms"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""  # trống = dùng REDIS_URL
    STORAGE_ROOT: Path = BACKEND_DIR / "storage"

    # Session / bảo mật (SDD mục 14)
    SESSION_BACKEND: str = "redis"  # redis | memory (memory chỉ cho dev/test, 1 tiến trình)
    SESSION_TTL_SECONDS: int = 8 * 3600
    SESSION_COOKIE_NAME: str = "dms_sid"
    # Trống = Secure khi staging/production. Đặt false CHỈ khi thử bản production qua http trong mạng nội bộ.
    SESSION_COOKIE_SECURE: bool | None = None
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_WINDOW_SECONDS: int = 900

    # Upload (D-01: chốt sau khi đo)
    MAX_UPLOAD_MB: int = 25
    MAX_PAGES: int = 100
    MAX_IMAGE_PIXELS: int = 60_000_000

    # Xóa mềm (D-05)
    SOFT_DELETE_RETENTION_DAYS: int = 30
    PURGE_INTERVAL_SECONDS: int = 24 * 3600

    # Job nền (FR-04, NFR-03)
    JOB_MAX_ATTEMPTS: int = 3
    JOB_RETRY_BACKOFF_SECONDS: int = 30
    JOB_STALE_SECONDS: int = 1800  # processing quá lâu (worker chết) -> nhận lại
    JOB_REQUEUE_AFTER_SECONDS: int = 600  # queued bị kẹt -> beat gửi lại
    REQUEUE_INTERVAL_SECONDS: int = 300

    # OCR
    OCR_ENGINE: str = "paddleocr"
    # P2-03: auto (vietocr nếu đã cài, không thì paddleocr-hw) | vietocr | paddleocr-hw (baseline)
    OCR_HW_ENGINE: str = "auto"
    OCR_HW_REC_MODEL: str = ""  # P2-03 paddleocr-hw: tên model nhận dạng (trống = mặc định theo ngôn ngữ)
    VIETOCR_CONFIG: str = "vgg_transformer"  # P2-03 vietocr: cấu hình/weights VietOCR
    VIETOCR_CACHE_DIR: str = ""  # nơi lưu cấu hình + weights VietOCR (trống = ~/.cache/vietocr)
    OCR_LANG: str = "vi"
    OCR_DEVICE: str = "cpu"
    OCR_RENDER_DPI: int = 200
    OCR_PRELOAD_ON_START: bool = True
    OCR_MODEL_SOURCE_CHECK: bool = False
    OCR_PREPROCESS_DENOISE: bool = False
    TEXT_LAYER_MIN_CHARS: int = 20
    # Trang có confidence (0-100) dưới ngưỡng -> needs_review. Hiệu chỉnh theo NFR-08 (D-06)
    NEEDS_REVIEW_THRESHOLD: float = 85.0

    # P2-05 phân loại, P2-07 mượn hồ sơ, P2-08 bulk import
    # Xác suất (0-1) của gợi ý cao nhất phải đạt ngưỡng mới hiển thị (UC-22 2a). Hiệu chỉnh bằng
    # eval/classification_eval.py trên tập mẫu thật.
    CLASSIFY_MIN_SCORE: float = 0.3
    CLASSIFY_MAX_TRAINING_DOCS: int = 300
    BORROW_REMIND_INTERVAL_SECONDS: int = 24 * 3600
    IMPORT_MAX_FILES: int = 200
    IMPORT_MAX_TOTAL_MB: int = 500  # tổng dung lượng sau giải nén
    IMPORT_MAX_ZIP_RATIO: int = 100  # chặn zip bomb: tỉ lệ nén tối đa mỗi file

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.is_production and self.SESSION_BACKEND != "redis":
            raise ValueError("Production bắt buộc SESSION_BACKEND=redis (ADR-AUTH-003)")
        unknown = self.features_enabled - set(ALL_FEATURES)
        if unknown:
            raise ValueError(f"FEATURES_ENABLED có cờ không hợp lệ: {sorted(unknown)}")
        return self

    @property
    def features_enabled(self) -> frozenset[str]:
        return frozenset(f.strip() for f in self.FEATURES_ENABLED.split(",") if f.strip())

    @property
    def is_production(self) -> bool:
        return self.APP_ENV in {"staging", "production"}

    @property
    def cookie_secure(self) -> bool:
        return self.is_production if self.SESSION_COOKIE_SECURE is None else self.SESSION_COOKIE_SECURE

    @property
    def broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def broker_transport_options(self) -> dict[str, object]:
        """Redis broker + acks_late: message chưa ack được giao lại sau visibility_timeout. Phải lớn hơn
        thời gian job dài nhất (JOB_STALE_SECONDS) + backoff retry, nếu không job dài bị chạy trùng."""
        if not self.broker_url.startswith(("redis://", "rediss://")):
            return {}
        return {
            "visibility_timeout": max(2 * self.JOB_STALE_SECONDS, 3600),
            "socket_connect_timeout": 3,
            "socket_timeout": 10,
            "health_check_interval": 30,
        }

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset(o.strip().rstrip("/") for o in self.ALLOWED_ORIGINS.split(",") if o.strip())

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.APP_TIMEZONE)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
