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
MAX_UPSCALE = 2.0


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


SKEW_WIDTH = 800  # ước lượng góc trên ảnh thu nhỏ: đủ chính xác 0,1°, nhanh


def _profile_score(binary: np.ndarray, angle: float) -> float:
    h, w = binary.shape
    rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rows = cv2.warpAffine(binary, rot, (w, h), flags=cv2.INTER_NEAREST).sum(axis=1, dtype=np.float64)
    return float(np.var(rows))


def estimate_skew(gray: np.ndarray) -> float:
    """Độ nghiêng của dòng chữ (độ, dương = nghiêng ngược chiều kim đồng hồ); xoay -góc để thẳng lại.

    Phương pháp hình chiếu ngang: góc xoay làm tổng mực theo từng hàng "nhọn" nhất (phương sai lớn nhất) là góc mà
    các dòng chữ nằm ngang. Lọc trung vị trước khi phân ngưỡng để điểm nhiễu của bản scan kém không chi phối (cách cũ
    dùng minAreaRect trên mọi điểm mực: nhiễu làm sai góc vài độ).
    """
    scale = min(1.0, SKEW_WIDTH / gray.shape[1])
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    binary = cv2.threshold(cv2.medianBlur(small, 3), 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    if int(binary.sum()) < 50:
        return 0.0
    steps = np.arange(-MAX_DESKEW_ANGLE, MAX_DESKEW_ANGLE + 0.01, 0.5).tolist()
    coarse = max(steps, key=lambda a: _profile_score(binary, a))
    fine = max(np.arange(coarse - 0.5, coarse + 0.51, 0.1).tolist(), key=lambda a: _profile_score(binary, a))
    return -round(float(fine), 2)  # xoay +fine làm thẳng -> chữ đang nghiêng -fine


def upscale_small(image: np.ndarray, min_width: int) -> np.ndarray:
    """GUIDE 9 phương án 2: ảnh trang hẹp hơn min_width (ảnh chụp, scan nén) được phóng to (tối đa 2 lần) để chữ và
    dấu đủ pixel cho bước dò dòng/nhận dạng. min_width = 0: tắt."""
    width = image.shape[1]
    if not min_width or width >= min_width:
        return image
    f = min(MAX_UPSCALE, min_width / width)
    return cv2.resize(image, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)


def preprocess(image_bgr: np.ndarray, *, denoise: bool | None = None) -> tuple[np.ndarray, float]:
    """Trả (ảnh đã xử lý, góc đã xoay). Ảnh kết quả là ảnh lưu làm ảnh trang,
    nên tọa độ bounding box của OCR khớp với ảnh hiển thị trên OCR Editor."""
    denoise = settings.OCR_PREPROCESS_DENOISE if denoise is None else denoise
    image_bgr = upscale_small(image_bgr, settings.OCR_UPSCALE_MIN_WIDTH)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    if denoise:
        gray = cv2.fastNlMeansDenoising(gray, h=15)
    angle = -estimate_skew(gray)  # góc xoay để thẳng lại (OpenCV: dương = ngược chiều kim đồng hồ)
    if MIN_DESKEW_ANGLE <= abs(angle) < MAX_DESKEW_ANGLE:  # chạm biên dải tìm: thường là phát hiện sai, không xoay
        h, w = gray.shape
        rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        gray = cv2.warpAffine(gray, rot, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255,))
    else:
        angle = 0.0
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), angle
