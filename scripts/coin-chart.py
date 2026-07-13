#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas>=2.0",
#     "matplotlib>=3.7",
#     "numpy",
# ]
# ///
"""4H 캔들 차트: SMA(20/60/200) + 일목균형표 구름."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 색상 테마
BG_COLOR = "#f8fafc"
PANEL_BORDER = "#e2e8f0"
TEXT_COLOR = "#334155"
MUTED_TEXT = "#64748b"

MA1_COLOR = "#38bdf8"   # SMA 20
MA2_COLOR = "#6366f1"   # SMA 60
MA3_COLOR = "#1e3a5f"   # SMA 200

CLOUD_BULL = "#86efac"
CLOUD_BEAR = "#fca5a5"

CANDLE_UP = "#22c55e"
CANDLE_UP_EDGE = "#16a34a"
CANDLE_DOWN = "#ef4444"
CANDLE_DOWN_EDGE = "#dc2626"

HIGHLIGHT_COLOR = "#f59e0b"
CLOSE_LINE_COLOR = "#94a3b8"

ICHIMOKU_DISPLACEMENT = 26
TENKAN_PERIOD = 9
KIJUN_PERIOD = 26
SENKOU_B_PERIOD = 52

_KOREAN_FONT: fm.FontProperties | None = None


def setup_korean_font() -> fm.FontProperties:
    """한글 폰트 파일을 직접 등록해 matplotlib/mplfinance 전역에 적용."""
    global _KOREAN_FONT
    if _KOREAN_FONT is not None:
        return _KOREAN_FONT

    # macOS / Windows / Linux 후보 경로
    candidate_paths: list[Path] = [
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/Library/Fonts/AppleGothic.ttf"),
        Path("/Library/Fonts/NanumGothic.ttf"),
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    ]

    # fontManager에 이미 등록된 한글 폰트 경로도 우선 탐색
    preferred_names = {
        "Apple SD Gothic Neo",
        "AppleGothic",
        "NanumGothic",
        "Malgun Gothic",
        "Noto Sans CJK KR",
    }
    for entry in fm.fontManager.ttflist:
        if entry.name in preferred_names:
            candidate_paths.insert(0, Path(entry.fname))

    seen: set[str] = set()
    for path in candidate_paths:
        path_str = str(path.resolve()) if path.exists() else str(path)
        if not path.exists() or path_str in seen:
            continue
        seen.add(path_str)

        try:
            fm.fontManager.addfont(path_str)
        except (OSError, ValueError):
            continue

        prop = fm.FontProperties(fname=path_str)
        family = prop.get_name()
        plt.rcParams.update(
            {
                "font.family": family,
                "font.sans-serif": [family, "DejaVu Sans"],
                "axes.unicode_minus": False,
            }
        )
        _KOREAN_FONT = prop
        return prop

    _KOREAN_FONT = fm.FontProperties()
    return _KOREAN_FONT


def load_ohlcv(csv_path: Path) -> pd.DataFrame:
    """CSV에서 OHLCV 데이터를 읽어 mplfinance용 DataFrame으로 반환."""
    df = pd.read_csv(
        csv_path,
        comment="#",
        parse_dates=["datetime"],
        index_col="datetime",
    )
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    df = df.sort_index()
    return df[["Open", "High", "Low", "Close", "Volume"]]


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """SMA 및 일목 구름 지표 계산."""
    out = df.copy()
    close = out["Close"]
    high = out["High"]
    low = out["Low"]

    out["sma20"] = close.rolling(20).mean()
    out["sma60"] = close.rolling(60).mean()
    out["sma200"] = close.rolling(200).mean()

    tenkan = (high.rolling(TENKAN_PERIOD).max() + low.rolling(TENKAN_PERIOD).min()) / 2
    kijun = (high.rolling(KIJUN_PERIOD).max() + low.rolling(KIJUN_PERIOD).min()) / 2
    senkou_b_raw = (high.rolling(SENKOU_B_PERIOD).max() + low.rolling(SENKOU_B_PERIOD).min()) / 2

    # DESCRIPTION.md: 26봉 앞(미래)으로 이동
    out["senkou_a"] = ((tenkan + kijun) / 2).shift(ICHIMOKU_DISPLACEMENT)
    out["senkou_b"] = senkou_b_raw.shift(ICHIMOKU_DISPLACEMENT)

    return out


def _normalize_freq(freq: str) -> str:
    """infer_freq가 'min'/'H'/'T' 등 숫자 없는 약어를 반환할 때 '1'을 붙임."""
    if freq[0].isdigit() or freq[0] in "+-":
        return freq
    return f"1{freq}"


def _extend_index_for_cloud(df: pd.DataFrame) -> pd.DatetimeIndex:
    """구름이 마지막 봉 이후 26봉까지 표시되도록 인덱스 확장."""
    freq = pd.infer_freq(df.index)
    if freq is None:
        delta = df.index[-1] - df.index[-2]
    else:
        delta = pd.Timedelta(_normalize_freq(freq))

    future = pd.date_range(
        start=df.index[-1] + delta,
        periods=ICHIMOKU_DISPLACEMENT,
        freq=delta,
    )
    return df.index.union(future)


def draw_ichimoku_cloud(ax: plt.Axes, df: pd.DataFrame, extended_index: pd.DatetimeIndex) -> None:
    """선행스팬 A/B 사이 영역을 상승(녹색)/하락(빨강) 구름으로 채움."""
    n = len(df)
    span_a = np.full(len(extended_index), np.nan)
    span_b = np.full(len(extended_index), np.nan)

    raw_a = ((df["High"].rolling(TENKAN_PERIOD).max() + df["Low"].rolling(TENKAN_PERIOD).min()) / 2
             + (df["High"].rolling(KIJUN_PERIOD).max() + df["Low"].rolling(KIJUN_PERIOD).min()) / 2) / 2
    raw_b = (df["High"].rolling(SENKOU_B_PERIOD).max() + df["Low"].rolling(SENKOU_B_PERIOD).min()) / 2

    for i in range(n):
        j = i + ICHIMOKU_DISPLACEMENT
        if j < len(extended_index):
            if not np.isnan(raw_a.iloc[i]):
                span_a[j] = raw_a.iloc[i]
                span_b[j] = raw_b.iloc[i]

    x = mdates.date2num(extended_index)
    valid = ~(np.isnan(span_a) | np.isnan(span_b))
    if not valid.any():
        return

    ax.fill_between(
        x,
        span_a,
        span_b,
        where=valid & (span_a >= span_b),
        facecolor=CLOUD_BULL,
        alpha=0.30,
        interpolate=True,
        linewidth=0,
        zorder=1,
    )
    ax.fill_between(
        x,
        span_a,
        span_b,
        where=valid & (span_a < span_b),
        facecolor=CLOUD_BEAR,
        alpha=0.30,
        interpolate=True,
        linewidth=0,
        zorder=1,
    )


def _candle_width(index: pd.DatetimeIndex) -> float:
    """날짜 축에서 캔들 몸통 너비(일 단위) 계산."""
    if len(index) < 2:
        return 0.4
    return 0.7 * (mdates.date2num(index[1]) - mdates.date2num(index[0]))


def draw_candlesticks(ax: plt.Axes, df: pd.DataFrame, highlight_index: int | None = None) -> None:
    """OHLC 캔들스틱을 구름 위에 그림."""
    width = _candle_width(df.index)

    for i, (ts, row) in enumerate(df.iterrows()):
        x = mdates.date2num(ts)
        o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]

        if highlight_index is not None and i == highlight_index:
            body_color = HIGHLIGHT_COLOR
            edge_color = HIGHLIGHT_COLOR
        elif c >= o:
            body_color = CANDLE_UP
            edge_color = CANDLE_UP_EDGE
        else:
            body_color = CANDLE_DOWN
            edge_color = CANDLE_DOWN_EDGE

        ax.plot([x, x], [l, h], color=edge_color, linewidth=1.0, solid_capstyle="round", zorder=4)

        body_bottom = min(o, c)
        body_height = max(abs(c - o), (h - l) * 0.02)
        ax.add_patch(
            plt.Rectangle(
                (x - width / 2, body_bottom),
                width,
                body_height,
                facecolor=body_color,
                edgecolor=edge_color,
                linewidth=1.2,
                zorder=5,
            )
        )


def draw_ma_lines(ax: plt.Axes, df: pd.DataFrame) -> None:
    """종가 실선 + SMA 실선을 캔들 위에 그림."""
    ax.plot(
        df.index,
        df["Close"],
        color=CLOSE_LINE_COLOR,
        linewidth=1.0,
        alpha=0.7,
        zorder=6,
    )
    ax.plot(df.index, df["sma20"], color=MA1_COLOR, linewidth=1.4, zorder=7)
    ax.plot(df.index, df["sma60"], color=MA2_COLOR, linewidth=1.8, zorder=7)
    ax.plot(df.index, df["sma200"], color=MA3_COLOR, linewidth=2.4, zorder=7)


def add_indicator_legend(ax: plt.Axes, font: fm.FontProperties) -> None:
    """좌하단에 MA·구름 지표 색인."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    line_entries = [
        (MA1_COLOR, 2.0, "MA1 (20)", "단기 추세 · 진입 타이밍"),
        (MA2_COLOR, 2.2, "MA2 (60)", "중기 추세 · 눌림목 지지선"),
        (MA3_COLOR, 2.6, "MA3 (200)", "장기 환경 필터"),
        (CLOSE_LINE_COLOR, 1.4, "종가선", "실시간 종가 추이"),
    ]
    patch_entries = [
        (CLOUD_BULL, "일목 구름", "26봉 선행 · 녹색일 때 매수"),
        (CANDLE_UP, "상승봉", "종가 ≥ 시가"),
        (CANDLE_DOWN, "하락봉", "종가 < 시가"),
    ]

    handles = [Line2D([0], [0], color=c, linewidth=w) for c, w, _, _ in line_entries]
    handles += [Patch(facecolor=c, edgecolor=c, label=t) for c, t, _ in patch_entries]

    labels = [f"{title}  —  {desc}" for _, _, title, desc in line_entries]
    labels += [f"{title}  —  {desc}" for _, title, desc in patch_entries]

    legend = ax.legend(
        handles,
        labels,
        loc="lower left",
        fontsize=8.5,
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor=PANEL_BORDER,
        borderpad=0.8,
        labelspacing=0.55,
        handlelength=2.4,
        prop=font,
    )
    legend.get_frame().set_linewidth(0.8)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)

    ax.text(
        0.99,
        0.02,
        "최소 필요 데이터: 4H 캔들 200봉 이상",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color=MUTED_TEXT,
        fontproperties=font,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor=PANEL_BORDER, alpha=0.94),
        zorder=10,
    )


def style_axes(ax: plt.Axes, font: fm.FontProperties) -> None:
    """축·눈금 스타일 정리."""
    ax.tick_params(colors=MUTED_TEXT, labelsize=9)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.xaxis.label.set_color(TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_color(PANEL_BORDER)
        spine.set_linewidth(0.8)


def plot_chart(df: pd.DataFrame, output: Path | None = None, show: bool = True) -> None:
    """캔들 + SMA + 일목 구름 차트 생성."""
    font = setup_korean_font()
    df = compute_indicators(df)
    extended_index = _extend_index_for_cloud(df)

    fig, ax = plt.subplots(figsize=(16, 9), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.grid(False)

    # 1) 구름 (맨 뒤)
    draw_ichimoku_cloud(ax, df, extended_index)

    # 2) 캔들스틱
    draw_candlesticks(ax, df, highlight_index=len(df) - 1)

    # 3) 종가 실선 + 이동평균 실선
    draw_ma_lines(ax, df)

    ax.set_xlim(mdates.date2num(extended_index[0]), mdates.date2num(extended_index[-1]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=0, ha="center")

    style_axes(ax, font)
    add_indicator_legend(ax, font)

    ax.set_title(
        "KRW-BTC · 4H · 200봉",
        fontsize=15,
        fontweight="bold",
        pad=14,
        fontproperties=font,
        color=TEXT_COLOR,
    )
    ax.set_ylabel("Price", fontproperties=font)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v/1e6:.1f}M"))

    fig.patch.set_facecolor(BG_COLOR)
    plt.tight_layout()

    if output:
        fig.savefig(
            output,
            dpi=150,
            bbox_inches="tight",
            facecolor=BG_COLOR,
        )
        print(f"저장: {output}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="4H 캔들 차트 (SMA + 일목 구름)")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent / "upbit_KRW-BTC_240m_200.csv",
        help="OHLCV CSV 경로",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent / "chart.png",
        help="저장할 이미지 경로",
    )
    parser.add_argument("--show", action="store_true", help="화면 표시")
    args = parser.parse_args()

    df = load_ohlcv(args.csv)
    if len(df) < 200:
        raise SystemExit(f"데이터가 부족합니다: {len(df)}봉 (최소 200봉 필요)")

    plot_chart(df, output=args.output, show=args.show)


if __name__ == "__main__":
    main()
