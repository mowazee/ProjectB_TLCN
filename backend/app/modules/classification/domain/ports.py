"""Port của bộ phân loại (P2-05). Adapter: infrastructure/sklearn_classifier.py (scikit-learn)."""

from typing import Protocol


class TextClassifier(Protocol):
    name: str
    n_docs: int  # số mẫu dùng để huấn luyện

    def predict(self, text: str, top_k: int = 3) -> list[tuple[int, float]]:
        """[(category_id, điểm 0..1)] giảm dần theo điểm; [] nếu văn bản không có đặc trưng."""
        ...
