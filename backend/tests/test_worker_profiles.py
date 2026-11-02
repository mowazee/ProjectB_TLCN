"""Worker chính nhận cả hàng đợi ocr_hw: nạp sẵn engine theo WORKER_OCR_PROFILES, bỏ qua profile chưa bật cờ."""

import pytest

from app.modules.ocr.application import engines
from app.shared.config import settings
from app.workers import celery_app


@pytest.fixture
def loaded(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(settings, "OCR_PRELOAD_ON_START", True)
    monkeypatch.setenv("WORKER_OCR_PROFILES", "print,handwriting")
    monkeypatch.setattr(engines, "get_engine", lambda profile: calls.append(profile))
    monkeypatch.setattr(celery_app.os, "_exit", lambda code: pytest.fail(f"worker thoát với mã {code}"))
    return calls


def test_preloads_print_and_handwriting_when_enabled(loaded, monkeypatch):
    monkeypatch.setattr(settings, "FEATURES_ENABLED", "handwriting")
    celery_app._on_worker_init()
    assert loaded == ["print", "handwriting"]


def test_skips_handwriting_when_flag_off_instead_of_exiting(loaded, monkeypatch):
    monkeypatch.setattr(settings, "FEATURES_ENABLED", "")
    celery_app._on_worker_init()  # trước đây: "Chưa đăng ký OCR profile" -> os._exit(1)
    assert loaded == ["print"]


def test_compose_worker_listens_handwriting_queue():
    from pathlib import Path

    yaml = pytest.importorskip("yaml")  # PyYAML đến cùng gói OCR (constraints.txt)

    compose = yaml.safe_load((Path(__file__).resolve().parents[2] / "compose.yaml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]
    assert "ocr_hw" in worker["command"][worker["command"].index("-Q") + 1].split(",")
    assert worker["environment"]["WORKER_OCR_PROFILES"] == "print,handwriting"
    assert "worker-hw" not in compose["services"]


def test_handwriting_engine_splits_lines_and_shares_print_detector(monkeypatch):
    from app.modules.ocr.infrastructure.engines import handwriting, vietocr

    seen = {}
    monkeypatch.setattr(
        vietocr.VietOcrEngine,
        "__init__",
        lambda self, crop, det_model=None, config=None: seen.update(crop=crop, det_model=det_model),
    )
    monkeypatch.setattr(settings, "OCR_DET_MODEL", "PP-OCRv5_mobile_det")
    monkeypatch.setattr(settings, "OCR_HW_DET_MODEL", "")
    handwriting.VietOcrHandwritingEngine()
    assert seen["det_model"] == "PP-OCRv5_mobile_det"  # trống -> dùng chung model dò dòng của chữ in
    assert seen["crop"].max_ratio == settings.OCR_VIETOCR_MAX_RATIO and seen["crop"].pad == 4  # chia dòng dài
    monkeypatch.setattr(settings, "OCR_HW_DET_MODEL", "PP-OCRv5_server_det")
    handwriting.VietOcrHandwritingEngine()
    assert seen["det_model"] == "PP-OCRv5_server_det"


def test_text_detector_loaded_once_per_model(monkeypatch):
    import sys
    import types

    from app.modules.ocr.infrastructure.engines import vietocr

    created = []
    fake = types.ModuleType("paddleocr")
    fake.TextDetection = lambda **kw: created.append(kw) or object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "paddleocr", fake)
    monkeypatch.setattr(vietocr, "_detectors", {})
    a = vietocr.text_detector("PP-OCRv5_mobile_det")
    assert vietocr.text_detector("PP-OCRv5_mobile_det") is a  # engine chữ in + chữ viết tay: một model
    vietocr.text_detector(None)
    assert created == [{"model_name": "PP-OCRv5_mobile_det"}, {}]
