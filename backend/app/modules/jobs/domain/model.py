"""Trạng thái job và lỗi job (SDD mục 6): queued -> processing -> completed | failed."""

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"  # job đã về queued, worker cần hẹn chạy lại
    SKIPPED = "skipped"  # không nhận được (đã xử lý, đang chạy nơi khác)


# Kind của lõi; P2/P3 thêm giá trị bằng migration riêng (EXTRACT, CLASSIFY, BULK_IMPORT; EMBED)
OCR = "OCR"
ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.PROCESSING)


CANCELLED = "CANCELLED"  # error_code của job bị người dùng dừng (status failed, chạy lại được)


class JobCancelled(Exception):
    """Handler/runner phát hiện job đã bị dừng giữa chừng: thôi xử lý, giữ nguyên trạng thái người dùng đặt."""


class JobError(Exception):
    """Handler ném lỗi này để báo mã lỗi ổn định và có nên thử lại hay không."""

    def __init__(self, code: str, message: str = "", *, retryable: bool = False) -> None:
        super().__init__(message or code)
        self.code = code
        self.retryable = retryable


# Thông điệp an toàn hiển thị cho người dùng; error_detail chỉ lưu nội bộ
ERROR_MESSAGES = {
    "QUEUE_UNAVAILABLE": "Không gửi được yêu cầu tới hàng đợi. Vui lòng thử lại sau.",
    "FILE_NOT_FOUND": "Không tìm thấy file gốc trong kho lưu trữ.",
    "FILE_CORRUPT": "File bị hỏng hoặc không đọc được.",
    "TOO_MANY_PAGES": "Tài liệu vượt quá số trang cho phép.",
    "OCR_ENGINE_UNAVAILABLE": "OCR engine chưa sẵn sàng.",
    "OCR_ALL_PAGES_FAILED": "Không nhận dạng được trang nào của tài liệu.",
    "MAX_ATTEMPTS_EXCEEDED": "Đã hết số lần thử xử lý.",
    "DOCUMENT_DELETED": "Tài liệu đã bị xóa trước khi được xử lý.",
    "NO_HANDLER": "Tính năng xử lý job này đang tắt.",
    "IMPORT_REJECTED": "Lô nhập bị từ chối (vượt giới hạn hoặc file nén không an toàn).",
    "INTERNAL_ERROR": "Lỗi hệ thống khi xử lý.",
    "CANCELLED": "Đã dừng theo yêu cầu. Các trang đã xử lý được giữ lại; bấm Chạy lại để xử lý lại từ đầu.",
}


def public_error_message(code: str | None) -> str | None:
    if not code:
        return None
    return ERROR_MESSAGES.get(code, ERROR_MESSAGES["INTERNAL_ERROR"])
