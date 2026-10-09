# Lệnh phát triển (Đặc tả đề tài v0.5 mục 4.10). Trên Windows không có make: xem GUIDE.md (lệnh PowerShell tương đương).
PY ?= backend/.venv/bin/python
FEATURES_ALL = workflow,highlight,handwriting,extraction,classification,versions,borrowing,notifications,imports,rollback

.PHONY: help dev up down migrate seed test test-all lint openapi types frontend-test e2e eval check

help:
	@echo "dev | up | down | migrate | seed | test | test-all | lint | openapi | types | frontend-test | e2e | eval | check"

dev:            ## Postgres/Redis/API/worker/beat qua Docker + Vite dev server
	docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis api worker beat
	cd frontend && npm run dev

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	cd backend && ../$(PY) -m alembic upgrade head

seed:
	cd backend && ../$(PY) scripts/seed_demo.py

test:           ## Bộ test backend (cờ P2 tắt)
	cd backend && ../$(PY) -m pytest -q

test-all:       ## NFR-09: bộ test với mọi cờ P2 bật
	cd backend && TEST_FEATURES=all ../$(PY) -m pytest -q

lint:
	cd backend && ../$(PY) -m ruff check . && ../$(PY) -m ruff format --check . && ../$(PY) -m mypy app && .venv/bin/lint-imports
	cd frontend && npm run lint && npm run typecheck && npm run format:check

openapi:        ## Xuất docs/openapi.json rồi sinh types React
	cd backend && ../$(PY) scripts/export_openapi.py
	cd frontend && npm run gen:api

types: openapi

frontend-test:
	cd frontend && npm test

e2e:            ## Playwright trên hệ thống đang chạy (BASE_URL, mặc định http://127.0.0.1:8080)
	$(PY) -m pytest tests/e2e -q

eval:           ## NFR-08: CER/WER trên tập test (xem backend/eval/README.md)
	cd backend && ../$(PY) eval/ocr_eval.py --split test --profile print

check: lint test test-all frontend-test
