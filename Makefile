# Coin Forge — 개발 명령 모음
PY ?= python

.PHONY: help install dev test lint fmt trader trader-once backtest api compose-up compose-down

help:
	@echo "install      의존성 설치 (.[dev,api])"
	@echo "test         pytest 실행"
	@echo "lint         ruff + mypy"
	@echo "trader-once  1회 사이클 실행 (paper)"
	@echo "backtest     백테스트 (CSV=경로, RESAMPLE=1 로 1m→4H)"
	@echo "api          대시보드 API 서버"
	@echo "compose-up   docker compose 기동"

install:
	$(PY) -m pip install -e ".[dev,api]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check coinforge tests
	$(PY) -m mypy coinforge

fmt:
	$(PY) -m ruff format coinforge tests

trader:
	$(PY) -m coinforge.cli.trader

trader-once:
	$(PY) -m coinforge.cli.trader --once

# 사용: make backtest CSV=scripts/btc_krw_1m_data.csv RESAMPLE=1
backtest:
	$(PY) -m coinforge.cli.backtest --csv $(CSV) $(if $(RESAMPLE),--resample,) -o output/backtest.json

api:
	$(PY) -m coinforge.cli.api

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down
