"""Đánh giá OCR theo NFR-08 / D-06 trên tập dữ liệu giữ riêng.

    python eval/ocr_eval.py --data eval/data --split test --profile print
    python eval/ocr_eval.py --data eval/data --split test --profile handwriting --types handwriting

Cấu trúc dữ liệu (KHÔNG commit dữ liệu thật, eval/data nằm trong .gitignore):
    eval/data/<split>/<loại>/<tên>.(png|jpg|pdf)  +  <tên>.gt.txt (text đúng, UTF-8)
    split: dev (hiệu chỉnh ngưỡng) | test (báo cáo); loại: digital_pdf | scan_clear | scan_hard | handwriting

Báo cáo: độ chính xác ký tự (1 - CER gộp), độ chính xác khi bỏ dấu (GUIDE 9.3: tách lỗi dấu khỏi lỗi chữ cái),
số ký tự lạ, WER, số mẫu, số trang, giây/trang, cấu hình máy, theo từng loại;
ghi thêm từng trang (confidence, CER) vào JSON để hiệu chỉnh ngưỡng (calibrate_threshold.py).
Mục tiêu D-06: scan in > 90%, chữ viết tay > 70%. PDF có lớp chữ báo cáo riêng (không qua OCR).
"""

import argparse
import json
import os
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("SESSION_BACKEND", "memory")

from metrics import cer, corpus_cer, corpus_cer_no_diacritics, corpus_wer, foreign_chars  # noqa: E402

TARGETS = {
    "scan_clear": 0.90,
    "scan_hard": 0.90,
    "synth_page_clear": 0.90,
    "synth_page_hard": 0.90,
    "synth_page_lowres": 0.90,
    "handwriting": 0.70,
}
IMAGE_EXT = {".png", ".jpg", ".jpeg"}


@dataclass
class PageResult:
    sample: str
    type: str
    page: int
    confidence: float | None
    cer: float
    seconds: float
    text_layer: bool


def _recognize_file(path: Path, profile: str) -> list[tuple[str, float | None, float, bool]]:
    """(text, confidence, giây, là text layer) cho từng trang - cùng pipeline với worker."""
    from app.modules.ocr.application import engines
    from app.modules.ocr.infrastructure import images, pdf
    from app.shared.config import settings

    engine = engines.get_engine(profile)
    out: list[tuple[str, float | None, float, bool]] = []
    if path.suffix.lower() == ".pdf":
        for p in pdf.render_pages(path, settings.OCR_RENDER_DPI):
            t0 = time.perf_counter()
            chars = sum(len("".join(ln.text.split())) for ln in p.lines)
            if profile == "print" and chars >= settings.TEXT_LAYER_MIN_CHARS:
                out.append(("\n".join(ln.text for ln in p.lines), None, time.perf_counter() - t0, True))
                continue
            processed, _ = images.preprocess(images.png_to_bgr(p.png))
            res = engine.recognize(processed)
            out.append((res.text, _f(res.confidence), time.perf_counter() - t0, False))
    else:
        t0 = time.perf_counter()
        processed, _ = images.preprocess(images.load_image_bgr(path))
        res = engine.recognize(processed)
        out.append((res.text, _f(res.confidence), time.perf_counter() - t0, False))
    return out


def _f(v: object) -> float | None:
    return float(v) if v is not None else None  # type: ignore[arg-type]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--split", default="test", choices=["dev", "test"])
    ap.add_argument("--profile", default="print", choices=["print", "handwriting"])
    ap.add_argument("--types", nargs="*", default=None, help="giới hạn loại (thư mục con)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    from app import registry
    from app.shared.config import settings

    if args.profile == "handwriting":
        settings.FEATURES_ENABLED = "handwriting"
    registry.activate()

    base = args.data / args.split
    if not base.exists():
        print(f"Không thấy {base}. Xem eval/README.md để chuẩn bị dữ liệu.")
        return 2
    pages: list[PageResult] = []
    pairs: dict[str, list[tuple[str, str]]] = {}
    for type_dir in sorted(d for d in base.iterdir() if d.is_dir()):
        if args.types and type_dir.name not in args.types:
            continue
        for f in sorted(type_dir.iterdir()):
            if f.suffix.lower() not in IMAGE_EXT | {".pdf"}:
                continue
            gt_file = f.with_suffix(".gt.txt")
            if not gt_file.exists():
                print(f"! bỏ qua {f.name}: thiếu {gt_file.name}")
                continue
            gt_pages = gt_file.read_text(encoding="utf-8").split("\f")  # nhiều trang: ngăn bằng \f
            results = _recognize_file(f, args.profile)
            hyp_all = []
            for i, (text, conf, sec, layer) in enumerate(results):
                ref = gt_pages[i] if i < len(gt_pages) else ""
                pages.append(PageResult(f.name, type_dir.name, i + 1, conf, cer(ref, text), sec, layer))
                hyp_all.append(text)
            pairs.setdefault(type_dir.name, []).append(("\n".join(gt_pages), "\n".join(hyp_all)))

    summary = {}
    for t, prs in pairs.items():
        tp = [p for p in pages if p.type == t]
        acc = 1 - corpus_cer(prs)
        summary[t] = {
            "samples": len(prs),
            "pages": len(tp),
            "char_accuracy": round(acc, 4),
            "char_accuracy_no_diacritics": round(1 - corpus_cer_no_diacritics(prs), 4),
            "foreign_chars": sum(foreign_chars(h) for _, h in prs),
            "cer": round(corpus_cer(prs), 4),
            "wer": round(corpus_wer(prs), 4),
            "seconds_per_page": round(sum(p.seconds for p in tp) / max(len(tp), 1), 3),
            "target": TARGETS.get(t),
            "pass": (acc > TARGETS[t]) if t in TARGETS else None,
        }
    from app.modules.ocr.application import engines

    eng = engines.get_engine(args.profile)
    report = {
        "split": args.split,
        "profile": args.profile,
        "engine": f"{getattr(eng, 'name', '?')} {getattr(eng, 'version', '')}".strip(),
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "device": settings.OCR_DEVICE,
            "dpi": settings.OCR_RENDER_DPI,
        },
        "by_type": summary,
        "pages": [asdict(p) for p in pages],
    }
    stamp = time.strftime("%Y%m%d_%H%M")
    out = args.out or Path(__file__).parent / "reports" / f"ocr_{args.split}_{args.profile}_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    head = f"{'loại':<14}{'mẫu':>5}{'trang':>7}{'acc(1-CER)':>12}{'bỏ dấu':>9}{'k.tự lạ':>9}{'WER':>8}{'s/trang':>9}"
    print(f"{head}  mục tiêu")
    for t, s in summary.items():
        flag = "" if s["target"] is None else (" ĐẠT" if s["pass"] else " CHƯA ĐẠT")
        print(
            f"{t:<14}{s['samples']:>5}{s['pages']:>7}{s['char_accuracy']:>12.2%}"
            f"{s['char_accuracy_no_diacritics']:>9.2%}{s['foreign_chars']:>9}{s['wer']:>8.3f}"
            f"{s['seconds_per_page']:>9.2f}  {s['target'] or '-'}{flag}"
        )
    print(f"Báo cáo: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
