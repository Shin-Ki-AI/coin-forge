# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "requests",
# ]
# ///

import argparse
import datetime
import os
import time

import pandas as pd
import requests

# 설정 내역
MARKET = "KRW-BTC"
CANDLE_MIN = 1  # 1분봉
URL = f"https://api.upbit.com/v1/candles/minutes/{CANDLE_MIN}"
FILE_NAME = "btc_krw_1m_data.csv"
FETCH_SIZE = 200  # 업비트 1회 최대로 가져올 수 있는 개수


def fetch_candles(to_datetime=None):
    params = {"market": MARKET, "count": FETCH_SIZE}
    if to_datetime:
        # 업비트 API 포맷: yyyy-MM-dd'T'HH:mm:ss'Z' 또는 yyyy-MM-dd HH:mm:ss
        params["to"] = to_datetime.strftime("%Y-%m-%d %H:%M:%S")

    response = requests.get(URL, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None


def main():
    parser = argparse.ArgumentParser(description="업비트에서 BTC 1분봉 데이터를 수집합니다.")
    parser.add_argument(
        "--years", "-y",
        type=float,
        default=1.0,
        help="수집할 데이터 기간 (년 단위, 기본값: 1.0)"
    )
    args = parser.parse_args()

    # 1년 = 365일 * 24시간 * 60분 = 525,600분
    minutes_per_year = 525600
    total_count = int(minutes_per_year * args.years)

    if total_count <= 0:
        print("기간(years)은 0보다 커야 합니다.")
        return

    all_candles = []
    # 데이터가 없거나 처음 시작할 때 사용할 기준 시각 (현재 시각)
    current_to = datetime.datetime.now()

    print(f"데이터 수집을 시작합니다. 기간: {args.years}년 (총 약 {total_count}개 봉)...")

    while len(all_candles) < total_count:
        data = fetch_candles(current_to)

        if not data:
            print("데이터를 더 이상 가져올 수 없거나 오류가 발생했습니다.")
            break

        # 필요한 필드만 튜플로 추출하여 저장 (메모리 사용량 대폭 감소)
        for candle in data:
            all_candles.append((
                candle["candle_date_time_utc"],
                candle["opening_price"],
                candle["high_price"],
                candle["low_price"],
                candle["trade_price"],
                candle["candle_acc_trade_volume"]
            ))

        print(f"현재 수집된 데이터 개수: {len(all_candles)} / {total_count}")

        # 가장 과거의 데이터 시간을 추출하여 다음 요청의 기준('to')으로 설정
        last_candle_time_str = data[-1]["candle_date_time_utc"]
        # '2026-07-02T09:45:00' 포맷 파싱
        last_candle_time = datetime.datetime.strptime(
            last_candle_time_str, "%Y-%m-%dT%H:%M:%S"
        )

        # 다음 루프를 위해 기준 시각 업데이트 (1초 차이를 두어 중복 방지)
        current_to = last_candle_time - datetime.timedelta(seconds=1)

        # 업비트 API 초당 호출 제한(초당 10회)을 피하기 위한 안전장치
        time.sleep(0.1)

    # 요청한 수만큼 슬라이싱
    if len(all_candles) > total_count:
        all_candles = all_candles[:total_count]

    # DataFrame 변환 및 컬럼 설정
    df_formatted = pd.DataFrame(
        all_candles,
        columns=["datetime", "open", "high", "low", "close", "volume"]
    )

    # 과거 데이터부터 정렬 (선택 사항)
    df_formatted = df_formatted.iloc[::-1].reset_index(drop=True)

    # CSV 저장
    df_formatted.to_csv(FILE_NAME, index=False)
    print(f"성공적으로 '{FILE_NAME}' 파일이 생성되었습니다.")


if __name__ == "__main__":
    main()
