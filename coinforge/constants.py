"""프로젝트 전역 상수 (PLAN.md · INDEX.md 와 동기화).

값 변경 시 docs/PLAN.md, docs/INDEX.md, docs/CHECKLIST.md 주석과 함께 갱신할 것.
"""

from __future__ import annotations

# --- 시장 / 타임프레임 ---------------------------------------------------------
MARKET = "KRW-BTC"
TIMEFRAME = "4H"
TIMEFRAME_MINUTES = 240
CANDLE_COUNT = 240  # MA200(200봉) + 여유 버퍼

# --- 이동평균 기간 (INDEX.md §1) ----------------------------------------------
MA_SHORT = 20   # MA1: 단기 추세 · 진입 타이밍
MA_MID = 60     # MA2: 중기 추세 · 눌림목 지지선
MA_LONG = 200   # MA3: 장기 환경 필터

# --- 일목균형표 (INDEX.md §2) --------------------------------------------------
TENKAN_PERIOD = 9        # 전환선 (구름 계산용)
KIJUN_PERIOD = 26        # 기준선 (구름 계산용)
SENKOU_B_PERIOD = 52     # 선행스팬 B
ICHIMOKU_DISPLACEMENT = 26  # 26봉 선행(미래) displacement

# --- 거래량 부가 조건 ----------------------------------------------------------
VOLUME_AVG_PERIOD = 20   # 직전 20봉 평균 거래량 비교

# --- 리스크 파라미터 (PLAN.md 자금관리) ---------------------------------------
RISK_PER_TRADE_PCT = 0.01     # 1% 룰: 1회 거래 최대 손실 = 총자산 1%
DAILY_LOSS_LIMIT_PCT = 0.03   # 일일 손실 3% 초과 시 당일 거래 중단
HARD_STOP_PCT = 0.03          # 비상 하드스탑 -3%
MAX_POSITIONS = 1             # 최대 동시 포지션

# --- 비중조절 / 포지션 사이징 (#3) --------------------------------------------
SIZING_MODE_RISK = "risk"     # 1% 룰: 손절거리 기반 수량
SIZING_MODE_FIXED = "fixed"   # 고정 비율: 자본의 일정 %를 주문금액으로
# 1회 주문금액 상한 = 자본의 30%. 손절이 가까워도 100% 올인되지 않게 막는 핵심 안전장치.
MAX_POSITION_PCT = 0.30
# fixed 모드에서 사용할 주문금액 비율(자본 대비).
FIXED_POSITION_PCT = 0.20

# --- R-Multiple 청산 배수 (AGENTS.md §6) --------------------------------------
PARTIAL_TAKE_R = 2.0          # 2R 도달 시 부분 익절
PARTIAL_TAKE_RATIO = 0.5      # 부분 익절 비율 50%
FULL_TAKE_R = 3.0             # 3R 도달 시 전량 익절

# --- D2: 눌림목 반등 정의 (CHECKLIST D2 제안 채택) ----------------------------
MA20_PULLBACK_LOOKBACK = 3    # MA20 눌림목: 직전 1~3봉
MA20_PULLBACK_TOL = 0.01      # MA20 ±1% 이내 터치
MA60_PULLBACK_LOOKBACK = 5    # MA60 깊은 눌림목: 직전 1~5봉
MA60_PULLBACK_TOL = 0.015     # MA60 ±1.5% 이내 터치

# --- 거래소 / API --------------------------------------------------------------
# 매수 시 수수료·라운딩 여유 (잔고 한도 매수가 fee 로 초과되지 않도록 예약)
FEE_BUFFER_PCT = 0.001
UPBIT_REST_BASE = "https://api.upbit.com"
UPBIT_MAX_RETRIES = 3
UPBIT_RATE_LIMIT_PER_SEC = 10
# 시장가 주문 후 실제 체결 내역 조회(폴링) — 슬리피지 측정을 위해 필수
UPBIT_ORDER_SETTLE_POLLS = 5      # get_order 최대 조회 횟수
UPBIT_ORDER_SETTLE_INTERVAL = 0.3 # 체결 대기 폴링 간격(초)

# --- 백테스트/paper 슬리피지 모델 ---------------------------------------------
# 시장가 체결 시 요청가 대비 불리하게 밀리는 정도(bp). 매수는 위로, 매도는 아래로.
# live 실측치로 캘리브레이션 권장. 0 이면 슬리피지 없음(과거 동작).
BACKTEST_SLIPPAGE_BP = 5.0

# --- 스케줄러 (D5) -------------------------------------------------------------
# 봉 마감 후 대기 초. REST는 완성봉을 즉시 주므로 타임스탬프로 완성봉을 고른다.
# 버퍼는 경계 근처 시계 오차 흡수용 최소치면 충분(과거 60초 → 10초).
SCHEDULER_BUFFER_SECONDS = 10

# --- 지정가 주문 (#3) ----------------------------------------------------------
ORDER_TYPE_MARKET = "market"
ORDER_TYPE_LIMIT = "limit"
# 지정가 접수 후 체결 대기 상한(초). 초과 시 취소하고 시장가로 폴백.
LIMIT_ORDER_WAIT_SECONDS = 30.0
# 지정가를 현재가에서 유리한 쪽으로 밀어 두는 정도(bp). 0 = 현재가에 지정.
LIMIT_ORDER_OFFSET_BP = 0.0
