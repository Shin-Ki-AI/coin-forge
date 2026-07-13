# AGENTS.md — Coin Forge 에이전트 협업 가이드

여러 AI 에이전트가 **Coin Forge** (업비트 BTC-KRW 4H 자동매매 시스템)를 병렬로 구현할 때 따르는 규칙과 맥락을 정의한다.

---

## 1. 프로젝트 한 줄 요약

감정 개입 없는 기계적 매매. 일목 구름 + 3중 SMA로 진입·청산하고, 1% 룰·서킷 브레이커로 자본을 보호한다.  
**기준 문서**: [docs/PLAN.md](docs/PLAN.md) · **작업 목록**: [docs/CHECKLIST.md](docs/CHECKLIST.md) · **지표 정의**: [docs/INDEX.md](docs/INDEX.md)

---

## 2. 기술 스택

| 영역 | 선택 | 비고 |
|------|------|------|
| 백엔드 | Go 1.22+ | 단일 바이너리, `cmd/` 다중 엔트리 |
| DB | MongoDB | 포지션·거래 로그·일일 PnL |
| 거래소 | **업비트** (KRW-BTC) | 주문·잔고는 업비트 REST API |
| 캔들 수집 | **UpbitBridge WebSocket** | 4H 봉 240개 버퍼 유지 |
| 인프라 | Docker Compose | app + mongo + (선택) api |
| 알림 | Telegram, PushOver | |
| 프론트 | TBD (Phase 8) | PLAN.md "TBU" — 착수 전 결정 |
| 백테스트 데이터 | `scripts/get_backdata.py` | 1분봉 → 4H 리샘플 |

**참조 구현**: [scripts/coin-chart.py](scripts/coin-chart.py) — SMA·일목 구름 계산의 정답 예시  
**캔들 수집**: [upbit-bridge](https://github.com/suapapa/upgit-bridge) — WebSocket으로 4H 캔들 240봉 수집

---

## 3. 디렉터리 구조 (목표)

에이전트는 아래 구조를 따른다. 없으면 Phase 1에서 생성.

```
coin-forge/
├── AGENTS.md
├── cmd/
│   ├── trader/          # 4H 메인 루프 (실거래·paper)
│   ├── backtest/        # 백테스트 CLI
│   └── api/             # HTTP/WebSocket 대시보드 API
├── internal/
│   ├── config/          # 환경변수·설정
│   ├── domain/          # Candle, Position, TradeLog, Indicators
│   ├── indicators/      # SMA, Ichimoku
│   ├── bridge/          # UpbitBridge WS 캔들 수집 (240봉)
│   ├── exchange/        # Upbit REST (주문·잔고) + mock
│   ├── strategy/        # 진입·방어·청산 평가
│   ├── risk/            # 사이징, 서킷 브레이커
│   ├── storage/         # MongoDB repository
│   ├── notify/          # Telegram, PushOver
│   └── engine/          # 오케스트레이터 (메인 루프)
├── docs/
│   ├── PLAN.md
│   ├── CHECKLIST.md
│   └── INDEX.md
├── scripts/             # Python 유틸 (데이터·차트)
├── docker-compose.yml
├── .env.example
└── Makefile
```

---

## 4. 워크스트림 (에이전트 역할 분담)

한 세션에서 **하나의 워크스트림**만 담당한다. 다른 스트림 파일을 불필요하게 수정하지 않는다.

| 워크스트림 | 패키지 | CHECKLIST Phase | 담당 범위 |
|-----------|--------|-----------------|-----------|
| `infra` | 루트, `docker/`, CI | 1, 12 | Go 모듈, Docker, Makefile, CI |
| `core` | `internal/domain`, `internal/config` | 2 | 타입·설정·상수 |
| `indicators` | `internal/indicators` | 3 | SMA, 일목, 거래량 |
| `bridge` | `internal/bridge` | 4.A | UpbitBridge WS, 240봉 버퍼 |
| `exchange` | `internal/exchange` | 4.B | 업비트 REST 주문·잔고, mock |
| `strategy` | `internal/strategy` | 5 | 진입·방어·청산 |
| `risk` | `internal/risk` | 6 | 1% 룰, 서킷 브레이커 |
| `storage` | `internal/storage` | 7 | MongoDB |
| `notify` | `internal/notify` | 8 | Telegram, PushOver |
| `engine` | `internal/engine`, `cmd/trader` | 9 | 스케줄러, 메인 루프 |
| `backtest` | `cmd/backtest`, `internal/backtest` | 10 | 백테스트·성과 지표 |
| `api` | `cmd/api` | 11.1 | REST/SSE |
| `frontend` | `web/` (생성 예정) | 11.2 | 대시보드 UI |

### 작업 착수 절차

1. [docs/CHECKLIST.md](docs/CHECKLIST.md)에서 `[ ]` 항목 중 **선행 조건이 충족된** 작업 선택
2. 해당 행을 `[~]`로 변경 (다른 에이전트와 중복 방지)
3. 구현 → 테스트 → 완료 시 `[x]`로 변경
4. 차단·결정 필요 시 `[!]` + 본 문서 **§8 미결정 사항**에 기록

---

## 5. 코딩 규칙

### Go

- `internal/` 패키지는 외부 import 불가 (표준 Go 레이아웃)
- 외부 의존(거래소, DB, 알림)은 **인터페이스**로 정의하고 main/engine에서 주입
- 에러는 wrap: `fmt.Errorf("fetch candles: %w", err)`
- 금액·수량은 `float64` 대신 **정수형 원화/사토시** 또는 `decimal` 라이브러리 검토 (라운딩 버그 방지)
- context 전파: API·DB 호출에 `context.Context` 필수

### 테스트

- 전략·지표·리스크: **테이블 드리븐** 단위 테스트 필수
- exchange·notify: mock 구현으로 engine 테스트
- `scripts/coin-chart.py` 산출값과 지표 수치 교차 검증 (Phase 3.6)

### 커밋

- 사용자가 요청할 때만 커밋
- 메시지: `feat(strategy): add entry gate 1 ichimoku filter` 형식
- `.env`, API 키 커밋 금지

### 범위

- 요청·체크리스트 항목만 수정. 무관한 리팩터링 금지
- 기존 Python 스크립트는 Go 이식 참고용 — 함부로 삭제·대체하지 않음

---

## 6. 도메인 규칙 (구현 시 반드시 준수)

### 지표 ([INDEX.md](docs/INDEX.md))

- **캔들 입력**: UpbitBridge WS 버퍼에서 4H 봉 **240개** (MA200 + 여유)
- SMA: 단순이동평균, 종가 기준, 기간 20/60/200
- 일목: 전환선(9)·기준선(26)은 구름 계산용만. **26봉 선행** displacement
- 구름 상단 = max(senkou_a, senkou_b), 하단 = min(...)
- Bull 구름: senkou_a > senkou_b

### 진입 (PLAN.md 3관문 + 방어)

모든 관문 통과 + 방어 미발동 시에만 매수.

1. 가격 > 구름 상단, bull 구름
2. MA200 < MA60 < MA20, 가격 > MA20
3. 눌림목 반등 — [CHECKLIST D2](docs/CHECKLIST.md) 제안안 적용 (미확정 시 strategy에 `// TODO(D2)` 표시)

**차단**: 구름 아래/내부/bear, MA200>MA60, 기존 포지션

### 청산 우선순위

동시 조건 시 **가장 보수적(손실 최소화)** 조건 우선:

1. 비상 하드스탑 −3%
2. MA60 이탈 / 구름 상단 이탈 (손절)
3. 2R 부분 익절 (50%)
4. 3R 또는 MA20 이탈 (전량 익절)

### 리스크

- 1회 거래 최대 손실 = 총 자산의 1%
- 일일 최대 손실 = 3% → 이후 당일 거래 중단
- 최대 동시 포지션 1개

### R-Multiple

- `1R = entry_price - stop_price` (롱 기준)
- `2R` = entry + 2×1R → 50% 청산
- `3R` = entry + 3×1R → 잔량 전량 청산

---

## 7. 환경 변수 (.env.example 템플릿)

```bash
# Upbit (주문·잔고)
UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=

# UpbitBridge (캔들 수집)
UPBIT_BRIDGE_WS_URL=ws://localhost:8080/ws
CANDLE_COUNT=240

# MongoDB
MONGO_URI=mongodb://mongo:27017/coinforge

# Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
PUSHOVER_USER_KEY=
PUSHOVER_API_TOKEN=

# Trading
MARKET=KRW-BTC
TRADING_MODE=paper          # paper | live
TOTAL_EQUITY_KRW=1000000    # paper 모드 초기 자본

# Risk
RISK_PER_TRADE_PCT=0.01
DAILY_LOSS_LIMIT_PCT=0.03
HARD_STOP_PCT=0.03
```

---

## 8. 미결정 사항 (에이전트가 해결·기록)

| ID | 질문 | 현재 권장 | 결정 시 업데이트 |
|----|------|-----------|------------------|
| D1 | 거래소 API | **업비트** (결정됨) | §2, CHECKLIST D1 |
| D4 | 4H 캔들 데이터 소스 | **UpbitBridge WebSocket, 240봉** (결정됨) | `internal/bridge`, CHECKLIST D4 |
| D2 | 눌림목 반등 정의 | CHECKLIST D2 제안안 | `internal/strategy/pullback.go` |
| D3 | 프론트 스택 | 미정 | `web/` 생성 시 |
| D5 | 스케줄러 정확 시점 | 4H 봉 마감 + 1분 버퍼 (WS 반영 지연) | `engine/scheduler.go` |

결정이 내려지면 해당 섹션과 CHECKLIST의 `[!]`를 `[x]`로 바꾼다.

---

## 9. 백테스트 게이트 (배포 차단 조건)

아래 미달 시 **live 모드 배포 금지**:

| 지표 | 최소값 |
|------|--------|
| 승률 (Win Rate) | 45% |
| 손익비 (Profit Factor) | 1.5 |

백테스트는 `internal/strategy`·`internal/risk`와 **동일 패키지**를 import해 로직 드리프트를 방지한다.

---

## 10. 알림 이벤트 스키마

모든 Notifier 구현체가 동일 struct 사용:

```go
type TradeEvent struct {
    Type        string  // "entry" | "exit" | "partial_exit" | "error" | "circuit_breaker"
    Market      string  // "KRW-BTC"
    Price       float64
    Quantity    float64
    StopPrice   float64
    Target2R    float64
    Target3R    float64
    PnLPercent  float64 // exit 시
    Reason      string  // 한글 가능, 로그와 동일 문자열
    Timestamp   time.Time
}
```

---

## 11. 로컬 개발 빠른 시작 (구현 완료 후)

```bash
cp .env.example .env
# .env 편집

docker compose up -d mongo
go run ./cmd/trader          # paper 모드
go run ./cmd/backtest --years 3
go test ./...
```

---

## 12. 에이전트 간 충돌 방지

- **동시 수정 금지**: 같은 CHECKLIST ID를 두 에이전트가 `[~]`로 두지 않음
- **인터페이스 먼저**: `bridge.CandleProvider`, `exchange.Exchange`, `storage.Repository`, `notify.Notifier`는 해당 워크스트림 담당자가 먼저 정의
- **Breaking change**: 인터페이스 변경 시 CHECKLIST에 메모 + 영향 워크스트림 명시
- **문서 동기화**: 동작·파라미터 변경 시 PLAN.md는 건드리지 않고 CHECKLIST·코드 주석에 반영 (PLAN.md는 아키텍처 원본)

---

## 13. 완료 정의 (Definition of Done)

워크스트림 작업 하나가 완료되려면:

- [ ] CHECKLIST 해당 ID가 `[x]`
- [ ] 단위 테스트 통과 (`go test ./internal/<package>/...`)
- [ ] `go vet`, `staticcheck` (또는 golangci-lint) 경고 없음
- [ ] 공개 함수에 GoDoc 한 줄 이상
- [ ] 다른 워크스트림이 의존하는 인터페이스가 `.go` 파일에 정의됨

---

## 14. 참고 링크

- [PLAN.md](docs/PLAN.md) — 아키텍처·매매 규칙 원본
- [CHECKLIST.md](docs/CHECKLIST.md) — 구현 작업·마일스톤
- [INDEX.md](docs/INDEX.md) — 지표 수식
- [차트 예제](refs/BTC-KRW_chart.jpg) — 대시보드 UI 목표
- [백데이터 스크립트](scripts/get_backdata.py)
