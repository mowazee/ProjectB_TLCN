"""Chỉ số NFR-08 (eval/metrics.py): CER tính lỗi mất dấu, chuẩn hóa khoảng trắng/NFC."""

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from metrics import cer, char_accuracy, corpus_cer, wer  # noqa: E402


def test_cer_counts_missing_diacritics():
    assert cer("Hợp đồng", "Hợp đồng") == 0
    assert cer("Hợp đồng", "Hop dong") == 3 / 8  # ợ, đ, ồ sai
    assert cer("abc", "") == 1 and cer("", "") == 0


def test_normalization():
    nfd = unicodedata.normalize("NFD", "Việt  Nam ")
    assert cer("Việt Nam", nfd) == 0 and wer("Việt Nam", "Việt  Nam") == 0
    assert char_accuracy("ab", "abcdef") == 0.0


def test_corpus_cer_weighted_by_length():
    pairs = [("aaaaaaaaaa", "aaaaaaaaab"), ("b", "c")]
    assert corpus_cer(pairs) == 2 / 11
