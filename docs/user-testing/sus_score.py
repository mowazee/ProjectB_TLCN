"""Tổng hợp kết quả thực nghiệm người dùng: điểm SUS, tỉ lệ hoàn thành tác vụ, thời gian, so sánh vòng 1 – vòng 2.

    python sus_score.py ket_qua_thuc_nghiem.csv --round 1
    python sus_score.py ket_qua_thuc_nghiem.csv --compare
Chỉ dùng thư viện chuẩn. Dòng có participant bắt đầu bằng "P00" (dòng ví dụ) bị bỏ qua.
"""

import argparse
import csv
import statistics
import sys

TASKS = [f"T{i}" for i in range(1, 10)]


def sus(row: dict[str, str]) -> float:
    total = 0
    for i in range(1, 11):
        v = int(row[f"q{i}"])
        if not 1 <= v <= 5:
            raise ValueError(f"{row['participant']}: q{i} phải từ 1 đến 5")
        total += (v - 1) if i % 2 else (5 - v)
    return total * 2.5


def summarize(rows: list[dict[str, str]]) -> dict[str, float]:
    scores = [sus(r) for r in rows]
    done = attempted = 0
    for r in rows:
        for t in TASKS:
            if r.get(t, "").strip() != "":
                attempted += 1
                done += int(r[t])
    times = [float(r["time_s"]) for r in rows if r.get("time_s")]
    errors = [int(r["errors"]) for r in rows if r.get("errors")]
    return {
        "n": len(rows),
        "sus_mean": statistics.mean(scores) if scores else 0.0,
        "sus_min": min(scores) if scores else 0.0,
        "sus_max": max(scores) if scores else 0.0,
        "task_success": done / attempted if attempted else 0.0,
        "time_mean_s": statistics.mean(times) if times else 0.0,
        "errors_mean": statistics.mean(errors) if errors else 0.0,
    }


def show(title: str, s: dict[str, float]) -> None:
    print(f"== {title}: {int(s['n'])} người")
    print(f"   SUS trung bình {s['sus_mean']:.1f} (thấp nhất {s['sus_min']:.1f}, cao nhất {s['sus_max']:.1f})")
    print(f"   Tỉ lệ hoàn thành tác vụ {s['task_success']:.0%}")
    print(f"   Thời gian trung bình {s['time_mean_s']:.0f} s, số lỗi thao tác trung bình {s['errors_mean']:.1f}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--round", type=int)
    ap.add_argument("--compare", action="store_true", help="so sánh vòng 1 và vòng 2")
    a = ap.parse_args()
    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("participant") and not r["participant"].startswith("P00")]
    if a.compare:
        r1 = summarize([r for r in rows if r["round"] == "1"])
        r2 = summarize([r for r in rows if r["round"] == "2"])
        show("Vòng 1", r1)
        show("Vòng 2", r2)
        print(
            f"== Thay đổi: SUS {r2['sus_mean'] - r1['sus_mean']:+.1f}; hoàn thành "
            f"{(r2['task_success'] - r1['task_success']) * 100:+.0f} điểm %; thời gian "
            f"{r2['time_mean_s'] - r1['time_mean_s']:+.0f} s"
        )
    else:
        sel = [r for r in rows if a.round is None or r["round"] == str(a.round)]
        show(f"Vòng {a.round}" if a.round else "Tất cả", summarize(sel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
