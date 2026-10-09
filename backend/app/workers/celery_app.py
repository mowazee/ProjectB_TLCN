"""Celery app cho worker và beat (cùng codebase với API).

Worker:  celery -A app.workers.celery_app:celery_app worker -Q default,ocr -P solo -l info
Worker chữ viết tay (P2-03, profile hw): ... worker -Q ocr_hw  (WORKER_OCR_PROFILES=handwriting)
Beat:    celery -A app.workers.celery_app:celery_app beat -l info
"""

import logging
import os
import socket
import sys
from typing import Any

from celery import Celery
from celery.signals import worker_init

from app.shared.config import settings

logger = logging.getLogger(__name__)
# Định danh worker ghi vào processing_jobs.worker_id ("<host>:<pid>"). Mỗi container một hostname; nhiều
# worker trên cùng một máy (không Docker) thì đặt WORKER_NAME khác nhau.
WORKER_HOST = os.environ.get("WORKER_NAME") or socket.gethostname()

celery_app = Celery("dms", broker=settings.broker_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_acks_late=True,  # worker chết giữa chừng thì message được giao lại (NFR-03)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,  # trạng thái job nằm ở processing_jobs
    task_serializer="json",
    accept_content=["json"],
    task_default_queue="default",
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,  # mất Redis thì worker chờ kết nối lại, không thoát
    broker_transport_options=settings.broker_transport_options,
    worker_cancel_long_running_tasks_on_connection_loss=False,  # job tự an toàn khi chạy lại (claim theo DB)
    timezone=settings.APP_TIMEZONE,
)


def _build_beat_schedule() -> dict[str, Any]:
    from app.workers.schedules import beat_schedule

    return beat_schedule()


celery_app.conf.beat_schedule = _build_beat_schedule()


@worker_init.connect
def _on_worker_init(**_: Any) -> None:
    """Nạp registry; nạp model OCR TRƯỚC khi nhận job. Lỗi thì dừng ngay (fail fast) để
    không nhận job rồi làm lỗi hàng loạt (PaddleX không khởi tạo lại được trong tiến trình)."""
    from app import registry
    from app.modules.jobs.application.queries import release_orphaned_jobs
    from app.modules.ocr.application import engines

    registry.activate()
    try:
        released = release_orphaned_jobs(WORKER_HOST)
        if released:
            logger.warning("Nhận lại %d job bị bỏ dở khi worker %s dừng đột ngột", released, WORKER_HOST)
    except Exception:  # DB chưa sẵn sàng: beat requeue_stuck_jobs vẫn nhận lại sau JOB_STALE_SECONDS
        logger.exception("Không kiểm tra được job bỏ dở")
    if not settings.OCR_PRELOAD_ON_START:
        return
    for profile in [p.strip() for p in os.environ.get("WORKER_OCR_PROFILES", "print").split(",") if p.strip()]:
        try:
            engines.get_engine(profile)
        except Exception as exc:
            msg = f"KHONG NAP DUOC OCR ENGINE '{profile}': {exc!r}. Worker dung; xem GUIDE.md muc su co OCR."
            logger.critical(msg, exc_info=True)
            print(msg, file=sys.stderr, flush=True)
            os._exit(1)
