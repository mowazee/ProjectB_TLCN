"""GUIDE 9.2 phương án 3: lọc ký tự lạ trong kết quả OCR. Python thuần (R3).

Model đa ngôn ngữ đôi khi chèn ký tự ngoài tiếng Việt (chữ Hán "图", chữ Latin mở rộng "ǎ"...) với độ tin cậy cao,
nên trang không rơi vào "cần xem lại". Ở đây: bỏ ký tự ngoài bảng chữ tiếng Việt + chữ số + dấu câu thông dụng, hạ
score dòng có ký tự bị bỏ và đếm số ký tự đã bỏ (OcrOutput.flagged_chars) để trang vào needs_review.
Chỉ che triệu chứng, không sửa được dấu: nguyên nhân gốc xử lý bằng engine VietOCR (phương án 1).
"""

import string
import unicodedata
from dataclasses import replace

from app.modules.ocr.domain.ports import OcrLine, OcrOutput

_TONES = ("", "̀", "́", "̉", "̃", "̣")  # huyền, sắc, hỏi, ngã, nặng


def _vietnamese_letters() -> frozenset[str]:
    letters = set(string.ascii_letters) | {"đ", "Đ"}
    for base in "aăâeêioôơuưy":
        for tone in _TONES:
            ch = unicodedata.normalize("NFC", base + tone)
            letters |= {ch, ch.upper()}
    return frozenset(letters)


LETTERS = _vietnamese_letters()
# Dấu câu và ký hiệu hay gặp trong văn bản hành chính, hợp đồng, hóa đơn
SYMBOLS = frozenset(string.punctuation + string.digits + "“”‘’–—…•·°²³±×÷€₫§©®™«»¼½¾№")
FLAGGED_SCORE = 0.5  # score tối đa của dòng có ký tự lạ (0-1)


def is_allowed(ch: str) -> bool:
    return ch in LETTERS or ch in SYMBOLS or ch.isspace()


def clean(text: str) -> tuple[str, int]:
    """(text đã bỏ ký tự lạ, số ký tự đã bỏ). Chuẩn hóa NFC trước: dấu tổ hợp rời được ghép vào chữ cái."""
    nfc = unicodedata.normalize("NFC", text)
    kept = [c for c in nfc if is_allowed(c)]
    return "".join(kept), len(nfc) - len(kept)


def sanitize(output: OcrOutput) -> OcrOutput:
    """Áp clean cho từng dòng; dòng có ký tự lạ bị hạ score còn tối đa FLAGGED_SCORE."""
    lines: list[OcrLine] = []
    flagged = 0
    for line in output.lines:
        text, removed = clean(line.text)
        if removed:
            flagged += removed
            score = min(line.score, FLAGGED_SCORE) if line.score is not None else None
            line = OcrLine(text, score, line.box)
        elif text != line.text:
            line = OcrLine(text, line.score, line.box)  # chỉ khác dạng chuẩn hóa NFC
        lines.append(line)
    return replace(output, lines=lines, flagged_chars=output.flagged_chars + flagged)
