"""Kiểm thử tải (phi chức năng) cho NFR-04: p95 GET/tìm kiếm ≤ 2 giây.

N người dùng ảo cùng lúc (mỗi người một phiên đăng nhập riêng), lặp các yêu cầu đọc phổ biến trong D giây:
danh sách tài liệu, tìm kiếm nội dung, chi tiết tài liệu, dashboard. In p50/p95/p99, số yêu cầu/giây, tỉ lệ lỗi; trả mã
thoát 1 nếu p95 vượt ngưỡng hoặc tỉ lệ lỗi > 1% (dùng được trong CI hoặc đối chiếu bản cam kết KPI).

Chạy khi hệ thống đang chạy (demo hoặc Docker), trong thư mục gốc repo:
    backend\\.venv\\Scripts\\python.exe tests/load/load_test.py --base http://127.0.0.1:8080 --users 20 --duration 60
Tài khoản: mặc định nhanvien / Demo@12345 (dữ liệu demo); đổi bằng --username/--password.
"""

# ruff: noqa: S311 - random chỉ để chọn yêu cầu mô phỏng, không dùng cho bảo mật
import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import defaultdict

import httpx

QUERIES = ["hợp đồng", "nghiem thu", "quyết định", "công văn", "báo cáo"]


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(p / 100 * len(values) + 0.5) - 1))
    return values[k]


async def login(client: httpx.AsyncClient, base: str, username: str, password: str) -> None:
    r = await client.post(
        f"{base}/api/auth/login", json={"username": username, "password": password}, headers={"Origin": base}
    )
    r.raise_for_status()


async def user_loop(base: str, args: argparse.Namespace, stop: float, stats: dict, errors: dict) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await login(client, base, args.username, args.password)
        docs = (await client.get(f"{base}/api/documents", params={"page_size": 20})).json().get("items", [])
        ids = [d["id"] for d in docs] or [None]
        while time.perf_counter() < stop:
            doc = random.choice(ids)
            detail = f"{base}/api/documents/{doc}" if doc else f"{base}/api/documents"
            choices: list[tuple[str, str, dict[str, str | int]]] = [
                ("GET /api/documents", f"{base}/api/documents", {"page_size": 20}),
                ("GET /api/search", f"{base}/api/search", {"q": random.choice(QUERIES)}),
                ("GET /api/documents/{id}", detail, {}),
                ("GET /api/dashboard", f"{base}/api/dashboard", {}),
            ]
            name, url, params = random.choice(choices)
            t0 = time.perf_counter()
            try:
                r = await client.get(url, params=params)
                ok = r.status_code < 400
            except httpx.HTTPError:
                ok = False
            dt = time.perf_counter() - t0
            stats[name].append(dt)
            if not ok:
                errors[name] += 1


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    ap = argparse.ArgumentParser(description="Kiểm thử tải NFR-04")
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--duration", type=int, default=60, help="giây")
    ap.add_argument("--username", default="nhanvien")
    ap.add_argument("--password", default="Demo@12345")
    ap.add_argument("--p95-ms", type=float, default=2000, help="ngưỡng p95 (NFR-04)")
    ap.add_argument("--json", help="ghi kết quả ra file JSON (minh chứng)")
    args = ap.parse_args()

    stats: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    start = time.perf_counter()
    stop = start + args.duration
    await asyncio.gather(*(user_loop(args.base, args, stop, stats, errors) for _ in range(args.users)))
    elapsed = time.perf_counter() - start

    rows, all_times, total_err = [], [], 0
    for name in sorted(stats):
        t = stats[name]
        all_times += t
        total_err += errors[name]
        rows.append(
            {
                "endpoint": name,
                "requests": len(t),
                "p50_ms": round(statistics.median(t) * 1000, 1),
                "p95_ms": round(pct(t, 95) * 1000, 1),
                "p99_ms": round(pct(t, 99) * 1000, 1),
                "errors": errors[name],
            }
        )
    summary = {
        "users": args.users,
        "duration_s": round(elapsed, 1),
        "requests": len(all_times),
        "rps": round(len(all_times) / elapsed, 1),
        "p95_ms": round(pct(all_times, 95) * 1000, 1),
        "error_rate": round(total_err / max(1, len(all_times)), 4),
        "endpoints": rows,
    }
    print(f"{'Endpoint':28} {'Số yêu cầu':>10} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8} {'Lỗi':>5}")
    for r in rows:
        print(
            f"{r['endpoint']:28} {r['requests']:>10} {r['p50_ms']:>8} {r['p95_ms']:>8} {r['p99_ms']:>8} {r['errors']:>5}"
        )
    print(
        f"\n{args.users} người dùng, {summary['duration_s']} s: {summary['requests']} yêu cầu "
        f"({summary['rps']}/s), p95 chung {summary['p95_ms']} ms, tỉ lệ lỗi {summary['error_rate']:.2%}"
    )
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    passed = summary["p95_ms"] <= args.p95_ms and summary["error_rate"] <= 0.01
    print("ĐẠT NFR-04" if passed else f"KHÔNG ĐẠT (ngưỡng p95 {args.p95_ms} ms, lỗi ≤ 1%)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
