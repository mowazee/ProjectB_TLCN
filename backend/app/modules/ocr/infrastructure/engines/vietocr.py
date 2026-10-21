"""Engine VietOCR: PaddleOCR chỉ DÒ DÒNG (TextDetection), VietOCR (huấn luyện riêng tiếng Việt) ĐỌC từng dòng.

Dùng cho chữ viết tay (P2-03) và, từ GUIDE 9 phương án 1, cho cả chữ in: bộ ký tự của VietOCR chỉ gồm chữ tiếng Việt
nên không chèn chữ Hán, và đọc dấu chồng ("ệ", "ổ", "ẫ") tốt hơn model PaddleOCR đa ngôn ngữ/latin.
Cài: backend/requirements-hw.txt (PyTorch CPU + vietocr --no-deps).
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.modules.ocr.domain.ports import OcrLine, OcrOutput
from app.modules.ocr.infrastructure.engines.paddle import _box
from app.shared.config import settings


def paddle_env() -> None:
    if not settings.OCR_MODEL_SOURCE_CHECK:
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def vietocr_cache_dir() -> Path:
    return Path(settings.VIETOCR_CACHE_DIR) if settings.VIETOCR_CACHE_DIR else Path.home() / ".cache" / "vietocr"


def prepare_vietocr(name: str | None = None) -> dict[str, Any]:
    """Cấu hình VietOCR dùng file trên đĩa: tải cấu hình + weights MỘT lần vào cache.

    vietocr gốc tải cấu hình từ internet mỗi lần khởi tạo (mất mạng -> worker không lên được) và để
    cnn.pretrained=True làm torchvision tải thêm ~550 MB weights ImageNet vô ích (sau đó bị weights
    VietOCR ghi đè). Ở đây: cấu hình lưu thành <tên>.yml, weights lưu cạnh đó, pretrained=False.
    """
    import requests
    import yaml
    from vietocr.tool.config import Cfg

    name = name or settings.VIETOCR_CONFIG
    cache = vietocr_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    cfg_path = cache / f"{name}.yml"
    if cfg_path.is_file():
        cfg = Cfg(yaml.safe_load(cfg_path.read_text(encoding="utf-8")))
    else:
        cfg = Cfg.load_config_from_name(name)
        cfg_path.write_text(yaml.safe_dump(dict(cfg), allow_unicode=True), encoding="utf-8")
    url = str(cfg["weights"])
    weights = cache / url.rsplit("/", 1)[-1] if url.startswith("http") else Path(url)
    if not weights.is_file():
        fd, tmp = tempfile.mkstemp(dir=cache, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f, requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            os.replace(tmp, weights)  # chỉ xuất hiện khi tải xong, không để file dở dang
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    cfg["weights"] = str(weights)
    cfg["cnn"]["pretrained"] = False
    cfg["device"] = "cuda" if settings.OCR_DEVICE.startswith("gpu") else "cpu"
    return dict(cfg)


def fix_quotes(text: str) -> str:
    """Bảng ký tự VietOCR không có ngoặc kép cong “ ” nên model đọc thành "?". Đổi "?" ở vị trí mở ngoặc (ngay
    trước một chữ/số) và dấu đóng tương ứng thành '"'; dấu hỏi thật ("không?") giữ nguyên."""
    out = list(text)
    is_open = False
    for i, ch in enumerate(out):
        prev = out[i - 1] if i else " "
        nxt = out[i + 1] if i + 1 < len(out) else " "
        if ch == '"':
            is_open = not is_open
        elif ch == "?" and not is_open and nxt.isalnum() and not prev.isalnum():
            out[i], is_open = '"', True
        elif ch == "?" and is_open and prev.isalnum() and not nxt.isalnum():
            out[i], is_open = '"', False
    return "".join(out)


@dataclass(frozen=True)
class LineCrop:
    """Cách cắt dòng trước khi đưa VietOCR.

    pad: nới khung (pixel) mọi phía. Đo trên văn bản scan thật (GUIDE 9): nới thêm trên/dưới theo chiều cao dòng làm
    KÉM đi (lấn nét chữ dòng kề) nên không dùng. max_ratio: chia dòng dài hơn tỷ lệ rộng/cao này tại khoảng trắng giữa
    các từ (split_points); None = không chia (chữ viết tay: dòng ngắn).
    """

    pad: int = 4
    max_ratio: float | None = None


def split_points(gray: np.ndarray, max_ratio: float) -> list[tuple[int, int]]:
    """Chia ảnh một dòng chữ thành các đoạn [x0, x1) có tỷ lệ rộng/cao <= max_ratio, cắt ở giữa khoảng trắng.

    VietOCR huấn luyện trên đoạn chữ ngắn: dòng văn bản A4 (~25:1) bị cụt đuôi khi giải mã. Khoảng trắng = cột
    không có điểm mực (ngưỡng Otsu); nếu trong vùng cho phép không có khoảng trắng nào thì cắt ở cột ít mực nhất.
    """
    import cv2

    h, w = gray.shape[:2]
    limit = max(int(h * max_ratio), 1)
    if w <= limit:
        return [(0, w)]
    ink = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1].sum(axis=0)
    out: list[tuple[int, int]] = []
    start = 0
    while w - start > limit:
        lo, hi = start + limit // 2, start + limit  # đoạn ít nhất nửa giới hạn để không sinh mảnh vụn
        window = ink[lo:hi]
        blank = np.flatnonzero(window == 0)
        if blank.size:
            # giữa của dải trắng dài nhất gần cuối cửa sổ
            runs = np.split(blank, np.flatnonzero(np.diff(blank) > 1) + 1)
            best = max(runs, key=lambda r: (len(r), r[-1]))
            cut = lo + int(best[len(best) // 2])
        else:
            cut = lo + int(np.argmin(window))
        out.append((start, cut))
        start = cut
    out.append((start, w))
    return out


class VietOcrEngine:
    name = "vietocr"

    def __init__(self, crop: LineCrop, det_model: str | None = None, config: str | None = None) -> None:
        paddle_env()
        from importlib.metadata import version

        from paddleocr import TextDetection
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        cfg = prepare_vietocr(config)
        self._crop = crop
        self._det = TextDetection(model_name=det_model) if det_model else TextDetection()
        self._rec = Predictor(Cfg(cfg))
        self.version: str | None = f"{version('vietocr')} {config or settings.VIETOCR_CONFIG}"  # engine_version

    def recognize(self, image_bgr: Any) -> OcrOutput:
        from PIL import Image

        out = OcrOutput(self.name, self.version)
        rgb = image_bgr[:, :, ::-1]
        height, width = rgb.shape[:2]
        polys: list[Any] = []
        for res in self._det.predict(image_bgr):
            polys.extend(res.get("dt_polys", []))
        boxes = sorted((_box(None, polys, i) for i in range(len(polys))), key=lambda b: (b[1] // 20, b[0]))
        boxes = [b for b in boxes if b[2] > 2 and b[3] > 2]
        crops: list[Any] = []
        owner: list[int] = []  # crops[i] thuộc dòng boxes[owner[i]]
        for i, (x, y, w, h) in enumerate(boxes):
            p = self._crop.pad
            x0, y0, x1, y1 = max(0, x - p), max(0, y - p), min(width, x + w + p), min(height, y + h + p)
            line = np.ascontiguousarray(rgb[y0:y1, x0:x1])
            parts = [(0, line.shape[1])]
            if self._crop.max_ratio:
                parts = split_points(np.ascontiguousarray(line[:, :, 0]), self._crop.max_ratio)
            for a, b in parts:
                crops.append(Image.fromarray(np.ascontiguousarray(line[:, a:b])))
                owner.append(i)
        if crops:
            texts, probs = self._rec.predict_batch(crops, return_prob=True)
            for i, box in enumerate(boxes):
                idx = [k for k, o in enumerate(owner) if o == i]
                text = " ".join(str(texts[k]).strip() for k in idx if str(texts[k]).strip())
                weight = sum(max(len(str(texts[k])), 1) for k in idx)
                prob = sum(float(probs[k]) * max(len(str(texts[k])), 1) for k in idx) / weight
                out.lines.append(OcrLine(fix_quotes(text), prob, box))
        return out
