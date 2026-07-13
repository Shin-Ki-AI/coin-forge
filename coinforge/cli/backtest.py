"""cmd/backtest — 백테스트 CLI (CHECKLIST 10.7).

CSV 백데이터를 로드해 전략을 순회 실행하고 성과 지표·배포 게이트를 출력한다.
게이트 미달 시 종료 코드 1 (CI/Make gate 용, 10.6).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..backtest.data import load_candles
from ..backtest.engine import BacktestEngine
from ..config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Coin Forge 백테스트")
    parser.add_argument("--csv", type=Path, required=True, help="OHLCV CSV 경로")
    parser.add_argument("--resample", action="store_true", help="1분봉 → 4H 리샘플")
    parser.add_argument("--equity", type=float, default=None, help="초기 자본 (KRW)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="리포트 JSON 저장 경로")
    args = parser.parse_args()

    config = load_config()
    if args.equity is not None:
        config.total_equity_krw = args.equity

    candles = load_candles(args.csv, resample=args.resample)
    if len(candles) < config.candle_count:
        print(f"캔들 부족: {len(candles)}봉 (최소 {config.candle_count}봉 필요)", file=sys.stderr)
        return 2

    report = BacktestEngine(candles, config).run()
    m = report.metrics

    print("=" * 56)
    print(" Coin Forge 백테스트 결과")
    print("=" * 56)
    print(f" 기간 봉 수      : {len(candles)}봉 (4H)")
    print(f" 총 거래 수      : {m.total_trades}")
    print(f" 승 / 패         : {m.wins} / {m.losses}")
    print(f" 승률            : {m.win_rate:.2%}   (기준 ≥ 45%)")
    pf = "∞" if m.profit_factor == float("inf") else f"{m.profit_factor:.2f}"
    print(f" 손익비(PF)      : {pf}   (기준 ≥ 1.5)")
    print(f" 최대 낙폭(MDD)  : {m.max_drawdown:.2%}")
    print(f" 순손익          : {m.net_pnl:,.0f} KRW")
    print(f" 최종 자산       : {m.final_equity:,.0f} KRW  ({m.return_pct:+.2%})")
    print("-" * 56)
    print(f" 배포 게이트     : {'✅ 통과' if report.gate_passed else '❌ 차단'}")
    print(f"                   {report.gate_reason}")
    print("=" * 56)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"리포트 저장: {args.output}")

    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
