"""OpenCV: cân chỉnh góc nghiêng (deskew), khử nhiễu, chuẩn hóa ảnh trước OCR.

Bản thử nghiệm và số liệu: notebooks/02_ocr_pipeline_exploration.ipynb.
"""

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.shared.config import settings
from app.shared.errors import InvalidInputError

MIN_DESKEW_ANGLE = 0.3  # độ; nhỏ hơn thì bỏ qua
MAX_DESKEW_ANGLE = 15.0  # lớn hơn thường là phát hiện sai, không xoay


def inspect_image(data: bytes) -> tuple[int, int]:
    """Kiểm tra ảnh đọc được và không quá lớn (chống decompression bomb)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidInputError("File ảnh bị hỏng hoặc không đọc được", code="FILE_CORRUPT") from exc
    if width * height > settings.MAX_IMAGE_PIXELS:
        raise InvalidInputError("Ảnh có độ phân giải quá lớn", code="IMAGE_TOO_LARGE")
    return width, height


def load_image_bgr(path: Path) -> np.ndarray:
    """Đọc ảnh, xoay theo EXIF, trả mảng BGR cho OpenCV/PaddleOCR."""
    with Image.open(path) as img:
        rgb = ImageOps.exif_transpose(img).convert("RGB")
        return np.asarray(rgb)[:, :, ::-1].copy()


def png_to_bgr(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise InvalidInputError("Không giải mã được ảnh", code="FILE_CORRUPT")
    return img


def encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Không mã hóa được PNG")
    return buf.tobytes()


def estimate_skew(gray: np.ndarray) -> float:
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0)).astype(np.float32)
    if len(coords) < 50:
        return 0.0
    angle = float(cv2.minAreaRect(coords)[-1])
    return angle - 90 if angle > 45 else angle


def preprocess(image_bgr: np.ndarray, *, denoise: bool | None = None) -> tuple[np.ndarray, float]:
    """Trả (ảnh đã xử lý, góc đã xoay). Ảnh kết quả là ảnh lưu làm ảnh trang,
    nên tọa độ bounding box của OCR khớp với ảnh hiển thị trên OCR Editor."""
    denoise = settings.OCR_PREPROCESS_DENOISE if denoise is None else denoise
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    if denoise:
        gray = cv2.fastNlMeansDenoising(gray, h=15)
    angle = estimate_skew(gray)
    if MIN_DESKEW_ANGLE <= abs(angle) <= MAX_DESKEW_ANGLE:
        h, w = gray.shape
        rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        gray = cv2.warpAffine(gray, rot, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255,))
    else:
        angle = 0.0
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), angle
