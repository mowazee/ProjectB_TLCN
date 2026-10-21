"""GUIDE 9 (cải thiện OCR tiếng Việt có dấu): lọc ký tự lạ (phương án 3), chọn engine chữ in (phương án 1),
chỉ số "lỗi dấu" cho eval (9.3)."""

import sys
import unicodedata
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.documents.infrastructure.models import DocumentPage
from app.modules.ocr.application import engines
from app.modules.ocr.domain.charset import FLAGGED_SCORE, LETTERS, clean, is_allowed, sanitize
from app.modules.ocr.domain.ports import OcrLine, OcrOutput, needs_review
from app.modules.ocr.infrastructure.models import OcrResult
from app.shared.config import settings
from tests.conftest import make_png, run_all_jobs, upload

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from metrics import corpus_cer, corpus_cer_no_diacritics, foreign_chars, normalize, strip_diacritics  # noqa: E402

VIETNAMESE = "Cộng hòa xã hội chủ nghĩa Việt Nam - Độc lập - Tự do - Hạnh phúc. Điều 3: “Khoản nợ” 32/2017/NĐ-CP (5%)"


def test_charset_keeps_all_vietnamese_letters():
    # a-zA-Z, đĐ, 12 nguyên âm x 6 thanh x hoa/thường, trừ 6 nguyên âm không dấu đã có trong a-z
    assert len(LETTERS) == 52 + 2 + (12 * 6 - 6) * 2
    assert clean(VIETNAMESE) == (VIETNAMESE, 0)
    assert all(is_allowed(c) for c in "ẮẰẲẴẶắằẳẵặỆệỔổẪẫỰựỸỹ₫°№…–—")


def test_charset_removes_foreign_chars():
    assert clean("ngày 06 tháng 01 n图m 2025") == ("ngày 06 tháng 01 nm 2025", 1)
    assert clean("nǎm Привет") == ("nm ", 7)  # ǎ (Latin mở rộng) và chữ Kirin
    nfd = unicodedata.normalize("NFD", "Việt")
    assert clean(nfd) == ("Việt", 0)  # dấu tổ hợp rời không bị coi là ký tự lạ


def test_sanitize_caps_score_and_flags_page():
    out = OcrOutput(
        "paddleocr",
        "x",
        [
            OcrLine("Hà Nội, ngày 06 tháng 01 n图m 2025", 0.98, (0, 0, 10, 10)),
            OcrLine("Quyết định", 0.97, (0, 20, 10, 10)),
        ],
    )
    assert not needs_review(out, 85)
    clean_out = sanitize(out)
    first, second = clean_out.lines
    assert first.text == "Hà Nội, ngày 06 tháng 01 nm 2025" and first.score == FLAGGED_SCORE
    assert second == out.lines[1]
    assert clean_out.flagged_chars == 1 and needs_review(clean_out, 85)
    assert out.flagged_chars == 0  # không sửa bản gốc


def test_pipeline_filters_foreign_chars_and_marks_review(seed, login, db, fake_engine, enqueued):
    fake_engine.lines = [
        OcrLine("Ngày 06 tháng 01 n图m 2025", 0.99, (20, 20, 300, 30)),
        OcrLine("Quyết định", 0.99, (20, 60, 250, 30)),
    ]
    c = login("officer")
    doc_id = upload(c, seed["category"].id, make_png(), "a.png").json()["document_id"]
    run_all_jobs(enqueued)
    db.rollback()
    page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == uuid.UUID(doc_id)))
    result = db.scalar(select(OcrResult).where(OcrResult.page_id == page.id))
    assert "图" not in result.raw_text and "nm 2025" in result.raw_text
    assert str(page.ocr_status) == "needs_review"  # độ tin cậy 0,99 nhưng có ký tự lạ


def test_print_engine_selection(monkeypatch):
    monkeypatch.setattr(settings, "OCR_ENGINE", "auto")
    monkeypatch.setattr(engines.importlib.util, "find_spec", lambda name: object() if name == "vietocr" else None)
    assert engines.resolved_print_engine() == "vietocr"
    monkeypatch.setattr(engines.importlib.util, "find_spec", lambda name: None)
    assert engines.resolved_print_engine() == "paddleocr"
    monkeypatch.setattr(settings, "OCR_ENGINE", "tesseract")
    with pytest.raises(ValueError, match="OCR_ENGINE"):
        engines._print_factory()


def test_get_engine_wraps_with_sanitizer(fake_engine):
    eng = engines.get_engine("print")
    assert (eng.name, eng.version) == ("fake", "1.0")
    fake_engine.lines = [OcrLine("a图b", 0.9, (0, 0, 1, 1))]
    assert eng.recognize(None).text == "ab"


def test_metrics_diacritics_gap():
    assert strip_diacritics("Điều 2. Đối tượng áp dụng") == "Dieu 2. Doi tuong ap dung"
    assert normalize("“Khoản nợ”") == '"Khoản nợ"'
    pairs = [("Cộng hòa xã hội", "Cong hoa xa hoi")]  # đúng hết chữ cái, sai hết dấu
    assert corpus_cer_no_diacritics(pairs) == 0 and corpus_cer(pairs) > 0.2
    assert foreign_chars("n图m Việt") == 1


def _line_image(words: int, word_w: int = 60, gap: int = 14, h: int = 40):
    import numpy as np

    img = np.full((h, 10 + words * (word_w + gap)), 255, np.uint8)
    for i in range(words):
        x = 10 + i * (word_w + gap)
        img[8 : h - 8, x : x + word_w] = 0  # "từ" = khối mực, giữa các từ là khoảng trắng
    return img


def test_split_points_cuts_long_lines_in_word_gaps():
    from app.modules.ocr.infrastructure.engines.vietocr import split_points

    short = _line_image(3)
    assert split_points(short, 12) == [(0, short.shape[1])]
    img = _line_image(20)  # ~1490 x 40: tỷ lệ ~37 > 12
    parts = split_points(img, 12)
    assert parts[0][0] == 0 and parts[-1][1] == img.shape[1]
    assert all(a == b for (_, a), (b, _) in zip(parts, parts[1:], strict=False))  # liền nhau, không mất cột
    assert all((b - a) <= 40 * 12 for a, b in parts)
    for _, cut in parts[:-1]:
        assert img[:, cut].min() == 255  # cắt đúng khoảng trắng, không cắt ngang chữ


def test_split_points_without_gaps_cuts_at_least_ink():
    import numpy as np

    from app.modules.ocr.infrastructure.engines.vietocr import split_points

    img = np.zeros((40, 1200), np.uint8)
    img[:, 400] = 255  # trong cửa sổ cắt đầu [240, 480) chỉ có một cột sáng
    parts = split_points(img, 12)
    assert parts[0] == (0, 400) and parts[-1][1] == 1200
    assert all(240 <= b - a <= 480 for a, b in parts[:-1])  # không khoảng trắng: cắt ở cột ít mực nhất


def test_fix_quotes_for_vietocr_vocab():
    from app.modules.ocr.infrastructure.engines.vietocr import fix_quotes

    assert fix_quotes("1. ?Khoản nợ vay? là") == '1. "Khoản nợ vay" là'
    assert fix_quotes('3. "Khoản nợ vay khác? là') == '3. "Khoản nợ vay khác" là'
    assert fix_quotes("Có đồng ý không?") == "Có đồng ý không?"
    assert fix_quotes("Vì sao? ?Bán nợ? là") == 'Vì sao? "Bán nợ" là'


@pytest.mark.parametrize("skew", [-3.0, -1.2, 0.8, 2.5])
def test_deskew_straightens_instead_of_doubling(skew):
    """Lỗi cũ: xoay cùng chiều độ nghiêng (1° thành 2°); nhiễu làm sai góc vài độ."""
    import cv2
    import numpy as np

    from app.modules.ocr.infrastructure import images

    page = np.full((1400, 1000), 255, np.uint8)
    for y in range(100, 1300, 45):  # các "dòng chữ": dải mực ngắt quãng như các từ
        for x in range(80, 900, 70):
            page[y : y + 18, x : x + 55] = 30
    rot = cv2.getRotationMatrix2D((500, 700), skew, 1.0)  # OpenCV: dương = ngược chiều kim đồng hồ
    tilted = cv2.warpAffine(page, rot, (1000, 1400), borderValue=255)
    noisy = np.clip(tilted.astype(np.int16) + np.random.default_rng(1).normal(0, 25, tilted.shape), 0, 255)
    gray = noisy.astype(np.uint8)
    assert abs(images.estimate_skew(gray) - skew) <= 0.2
    out, angle = images.preprocess(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
    assert abs(angle + skew) <= 0.2  # xoay ngược lại đúng góc nghiêng
    assert abs(images.estimate_skew(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY))) <= 0.2
