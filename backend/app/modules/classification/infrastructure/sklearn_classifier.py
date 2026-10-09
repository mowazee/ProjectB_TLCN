"""Bộ phân loại scikit-learn: TF-IDF + Logistic Regression (Đặc tả đề tài v0.5 mục 2: "scikit-learn (TF-IDF +
mô hình tuyến tính) làm baseline"; SDD P2-05, UC-22).

- TfidfVectorizer dùng tokenizer của domain (bỏ dấu, stopword, bigram), sublinear_tf.
- LogisticRegression class_weight="balanced": số tài liệu mỗi danh mục chênh lệch nhiều; predict_proba cho
  điểm 0..1 so được với ngưỡng CLASSIFY_MIN_SCORE (UC-22 bước 2a).
- Huấn luyện lại mỗi job CLASSIFY trên tối đa CLASSIFY_MAX_TRAINING_DOCS tài liệu (vài trăm mẫu → < 1 giây),
  nên không cần lưu/nạp model và danh mục mới/ngừng dùng có hiệu lực ngay.

scikit-learn chỉ được import khi gọi train() (trong worker), API không phải nạp scipy/sklearn.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.modules.classification.domain.text import tokenize

MODEL_NAME = "sklearn-tfidf-logreg-v1"


@dataclass
class _Fixed:
    """Chỉ có 0 hoặc 1 danh mục có mẫu: không huấn luyện được mô hình phân biệt."""

    label: int | None
    n_docs: int
    name: str = MODEL_NAME

    def predict(self, text: str, top_k: int = 3) -> list[tuple[int, float]]:
        if self.label is None or not tokenize(text):
            return []
        return [(self.label, 1.0)][:top_k]


@dataclass
class SklearnClassifier:
    pipeline: Any
    n_docs: int
    name: str = MODEL_NAME

    def predict(self, text: str, top_k: int = 3) -> list[tuple[int, float]]:
        if not tokenize(text):
            return []
        proba = self.pipeline.predict_proba([text])[0]
        ranked = sorted(
            ((int(label), float(p)) for label, p in zip(self.pipeline.classes_, proba, strict=True)),
            key=lambda x: (-x[1], x[0]),
        )
        return ranked[:top_k]


def train(samples: Iterable[tuple[int, str]]) -> SklearnClassifier | _Fixed:
    data = [(label, text) for label, text in samples if tokenize(text)]
    labels = {label for label, _ in data}
    if len(labels) < 2:
        return _Fixed(next(iter(labels), None), len(data))

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    pipeline = make_pipeline(
        TfidfVectorizer(analyzer=tokenize, sublinear_tf=True),
        LogisticRegression(C=10.0, class_weight="balanced", max_iter=2000),
    )
    pipeline.fit([text for _, text in data], [label for label, _ in data])
    return SklearnClassifier(pipeline, len(data))
