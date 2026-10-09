"""Gửi job sang hàng đợi Celery bằng tên task.

Dùng Celery client riêng chỉ để gửi, không import app.workers: API và các module lõi không phụ thuộc
code worker/OCR (R5). Worker đăng ký task cùng tên "jobs.run".
"""

import uuid
from functools import lru_cache

from celery import Celery

from app.shared.config import settings

RUN_TASK = "jobs.run"


@lru_cache(maxsize=1)
def _producer() -> Celery:
    app = Celery("dms-producer", broker=settings.broker_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_default_queue="default",
        broker_transport_options=settings.broker_transport_options,
        broker_connection_timeout=3,
        # Broker lỗi: thử lại ngắn rồi báo lỗi (create.send_or_fail đánh dấu QUEUE_UNAVAILABLE)
        # thay vì giữ request API vài chục giây.
        task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1},
    )
    return app


def send(job_id: uuid.UUID, queue: str, *, countdown: int | None = None) -> None:
    _producer().send_task(RUN_TASK, args=[str(job_id)], queue=queue, countdown=countdown)
