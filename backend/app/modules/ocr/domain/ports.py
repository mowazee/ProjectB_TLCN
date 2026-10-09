"""Port OcrEngine (Đặc tả đề tài v0.5 mục 4.3): OCR in (MVP) và chữ viết tay (P2-03) là hai
adapter cùng hợp đồng. Python thuần (R3)."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

TEXT_LAYER_ENGINE = "pymupdf"


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float | None  # 0-1 theo model; None với text layer
    box: tuple[int, int, int, int]  # x, y, w, h theo pixel ảnh trang


@dataclass
class OcrOutput:
    engine: str
    engine_version: str | None
    lines: list[OcrLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(ln.text for ln in self.lines if ln.text.strip())

    @property
    def confidence(self) -> Decimal | None:
        """Trung bình score có trọng số theo độ dài dòng, thang 0-100 (KHÔNG phải accuracy)."""
        scored = [(ln.score, len(ln.text)) for ln in self.lines if ln.score is not None]
        weight = sum(n for _, n in scored)
        if not scored or weight == 0:
            return None
        return Decimal(str(round(sum(s * n for s, n in scored) / weight * 100, 2)))

    @property
    def is_text_layer(self) -> bool:
        return self.engine == TEXT_LAYER_ENGINE

    @property
    def engine_label(self) -> str:
        """Giá trị ocr_results.engine_version, ví dụ 'paddleocr 3.7.0'."""
        return f"{self.engine} {self.engine_version}" if self.engine_version else self.engine

    def boxes_json(self) -> list[dict[str, Any]]:
        return [{"text": ln.text, "score": ln.score, "box": list(ln.box)} for ln in self.lines]


class OcrEngine(Protocol):
    name: str
    version: str | None

    def recognize(self, image_bgr: Any) -> OcrOutput: ...


def needs_review(output: OcrOutput, threshold: float) -> bool:
    """UC-02 bước 6: trang OCR có confidence dưới ngưỡng (hoặc rỗng) -> needs_review."""
    if output.is_text_layer:
        return False
    conf = output.confidence
    return conf is None or float(conf) < threshold or not output.text.strip()
