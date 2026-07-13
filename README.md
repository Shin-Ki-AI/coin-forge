# Coin Forge — 암호화폐 자동 매매 시스템 (Python)

업비트 **KRW-BTC 4시간봉** 기반 기계적 자동매매 시스템. 일목 구름 + 3중 SMA로
진입·청산하고, 1% 룰·서킷 브레이커로 자본을 보호한다.

> 언어: **Python 3.10+** (원 설계 문서의 Go → Python 이식). 지표 수식·매매 규칙·
> 백테스트 게이트는 [docs/PLAN.md](docs/PLAN.md)·[docs/INDEX.md](docs/INDEX.md)와 동일.

## 구조

```
coinforge/
├── config.py / constants.py   # 설정·상수
├── domain/                     # Candle, Indicators, Position, TradeLog
├── indicators/                 # SMA, 일목 구름, 거래량 (coin-chart.py 이식)
├── strategy/                   # 진입 3관문·방어·청산 (+ D2 눌림목)
├── risk/                       # 1% 룰 사이징, 서킷 브레이커
├── bridge/                     # 캔들 수집 (업비트 REST / Mock)
├── exchange/                   # 주문·잔고 (업비트 REST + JWT / Mock)
├── notify/                     # Telegram, PushOver, Mock
├── storage/                    # MongoDB / InMemory 저장소
├── engine/                     # 오케스트레이터 + 4H 스케줄러
├── backtest/                   # 백테스트 엔진·성과 지표·게이트
├── api/                        # FastAPI 대시보드 API
└── cli/                        # trader / backtest / api 엔트리포인트
```

## 설치

```bash
python -m venv .venv && . .venv/Scripts/activate   # (Windows: .venv\Scripts\activate)
pip install -e ".[dev,api]"
cp .env.example .env    # 편집: API 키, MONGO_URI, 알림 토큰
```

## 실행

```bash
# 테스트
make test                       # 또는: python -m pytest

# paper 트레이딩 (실시장 데이터, 실주문 없음)
python -m coinforge.cli.trader --once      # 1회 사이클
python -m coinforge.cli.trader             # 4H 루프 상주

# 백테스트 (게이트 미달 시 종료코드 1)
python -m coinforge.cli.backtest --csv scripts/btc_krw_1m_data.csv --resample -o output/bt.json

# 대시보드 API
python -m coinforge.cli.api                # http://localhost:8000/api/status

# 전체 스택 (mongo + app + api)
docker compose up -d --build
```

## 매매 규칙 요약

- **진입**(3관문 모두 통과 + 방어 미발동): ①가격>구름상단 & 상승구름 ②MA200<MA60<MA20 & 가격>MA20 ③MA20/MA60 눌림목 반등
- **청산**(보수적 우선순위): ①하드스탑 −3% ②MA60/구름상단 이탈 손절 ③2R 50% 부분익절 ④3R/MA20 이탈 전량익절
- **리스크**: 1회 손실 ≤ 자산 1%, 일일 손실 ≥ 3% 시 당일 중단, 최대 1 포지션
- **배포 게이트**: 백테스트 승률 ≥ 45% AND 손익비 ≥ 1.5 (미달 시 live 배포 차단)

## Reference

- [upbit-bridge](https://github.com/suapapa/upgit-bridge)
- [docs/PLAN.md](docs/PLAN.md) · [docs/CHECKLIST.md](docs/CHECKLIST.md) · [docs/INDEX.md](docs/INDEX.md)
