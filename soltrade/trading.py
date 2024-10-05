import asyncio
import pandas as pd
import requests
import os
import sys
from tabulate import tabulate
from apscheduler.schedulers.background import BlockingScheduler

from soltrade.config import config
from soltrade.log import log_general, log_transaction
from soltrade.strategy import (
    strategy,
    calc_stoploss,
    calc_trailing_stoploss,
    calc_entry_price,
)
from soltrade.transactions import perform_swap, market
from soltrade.wallet import find_balance

market("data/position.csv")


# Pulls the candlestick information in fifteen minute intervals
def fetch_candlestick() -> dict:
    url = "https://min-api.cryptocompare.com/data/v2/histominute"
    headers = {"authorization": config().api_key}
    params = {
        "tsym": config().primary_mint_symbol,
        "fsym": config().secondary_mint_symbol,
        "limit": 50,
        "aggregate": config().trading_interval_minutes,
    }
    response = requests.get(url, headers=headers, params=params)
    if response.json().get("Response") == "Error":
        log_general.error(response.json().get("Message"))
        exit()
    return response.json()


def perform_analysis():
    log_general.debug("Soltrade is analyzing the market; no trade has been executed.")
    market_instance = market()
    market_instance.load_position()
    candle_json = fetch_candlestick()
    candle_dict = candle_json["Data"]["Data"]
    columns = ["close", "high", "low", "open", "time"]
    new_df = pd.DataFrame(candle_dict, columns=columns)
    new_df["time"] = pd.to_datetime(new_df["time"], unit="s")
    new_df = strategy(new_df)
    data_file_path = "data/data.csv"

    try:
        existing_df = read_dataframe_from_csv(data_file_path)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(
            subset="time", keep="last"
        )

        second_to_last_index = new_df.index[-2]

        df = pd.concat(
            [
                new_df.iloc[:second_to_last_index],
                combined_df,
                new_df.iloc[second_to_last_index:],
            ]
        ).drop_duplicates(subset="time", keep="last")

        if "entry_price" in df.columns:
            df["entry_price"] = df.iloc[0]["entry_price"]
        if "stoploss" in df.columns:
            df["stoploss"] = df.iloc[0]["stoploss"]
        if "trailing_stoploss" in df.columns:
            df["trailing_stoploss"] = df.iloc[0]["trailing_stoploss"]
        if "trailing_stoploss_target" in df.columns:
            df["trailing_stoploss_target"] = df.iloc[0]["trailing_stoploss_target"]
    except FileNotFoundError:
        df = new_df

    last_row = df.iloc[[-2]]

    last_row = last_row.drop(columns=["high", "low", "open", "time"])

    custom_headers = {
        "close": "Price",
        "ema_s": "EMA Short",
        "ema_m": "EMA Medium",
        "upper_bband": "Upper Bollinger Band",
        "lower_bband": "Lower Bollinger Band",
        "rsi": "RSI",
        "entry": "Entry Signal",
        "exit": "Exit Signal",
        "entry_price": "Entry Price",
        "stoploss": "Stoploss",
        "trailing_stoploss": "Trailing Stoploss",
        "trailing_stoploss_target": "Trailing Stoploss Target",
    }

    last_row = last_row.rename(columns=custom_headers)
    # print(last_row)
    print(tabulate(last_row.T, headers="keys", tablefmt="rounded_grid"))

    config_instance = config()
    primary_mint = config_instance.primary_mint
    primary_mint_symbol = config_instance.primary_mint_symbol
    secondary_mint = config_instance.secondary_mint
    secondary_mint_symbol = config_instance.secondary_mint_symbol

    if not market_instance.position:
        input_amount = find_balance(primary_mint)
        if df["entry"].iloc[-1] == 1:
            if input_amount <= 0:
                log_transaction.info(
                    f"Soltrade has detected a buy signal, but does not have enough ${primary_mint_symbol} to trade."
                )
                return
            log_transaction.info(
                f"Soltrade has detected a buy signal using {input_amount} ${primary_mint_symbol}."
            )
            is_swapped = asyncio.run(perform_swap(input_amount, primary_mint))
            if is_swapped:
                df = calc_entry_price(df)
                df = calc_stoploss(df)
                df = calc_trailing_stoploss(df)
                print(tabulate(last_row.T, headers="keys", tablefmt="rounded_grid"))
                takeprofit = df["close"].iat[-1] * 1.25
                market_instance.update_position(
                    True, df["stoploss"].iloc[-1], takeprofit
                )
            save_dataframe_to_csv(df, data_file_path)
            return

    else:
        input_amount = find_balance(secondary_mint)
        df = calc_trailing_stoploss(df)
        stoploss = df["stoploss"].iloc[-1]
        trailing_stoploss = df["trailing_stoploss"].iloc[-1]

        if df["close"].iloc[-1] <= stoploss:
            log_transaction.info(
                f"Soltrade has detected a sell signal for {input_amount} ${secondary_mint_symbol}. Stoploss has been reached."
            )
            asyncio.run(perform_swap(input_amount, secondary_mint))
            stoploss = takeprofit = 0
            market_instance.update_position(False, stoploss, takeprofit)
            df = df.drop(
                columns=[
                    "stoploss",
                    "entry_price",
                    "trailing_stoploss",
                    "trailing_stoploss_target",
                ]
            )

        elif trailing_stoploss is not None and df["close"].iloc[-1] < trailing_stoploss:
            log_transaction.info(
                f"Soltrade has detected a sell signal for {input_amount} ${secondary_mint_symbol}. Trailing stoploss has been reached."
            )
            asyncio.run(perform_swap(input_amount, secondary_mint))
            stoploss = takeprofit = 0
            market_instance.update_position(False, stoploss, takeprofit)
            df = df.drop(
                columns=[
                    "stoploss",
                    "entry_price",
                    "trailing_stoploss",
                    "trailing_stoploss_target",
                ]
            )

        elif df["exit"].iloc[-1] == 1:
            log_transaction.info(
                f"Soltrade has detected a sell signal for {input_amount} ${secondary_mint_symbol}."
            )
            asyncio.run(perform_swap(input_amount, secondary_mint))
            stoploss = takeprofit = 0
            market_instance.update_position(False, stoploss, takeprofit)
            df = df.drop(
                columns=[
                    "stoploss",
                    "entry_price",
                    "trailing_stoploss",
                    "trailing_stoploss_target",
                ]
            )

        save_dataframe_to_csv(df, data_file_path)


def start_trading():
    log_general.info("Soltrade has now initialized the trading algorithm.")
    trading_sched = BlockingScheduler()
    trading_sched.add_job(
        perform_analysis,
        "interval",
        seconds=config().price_update_seconds,
        max_instances=1,
    )
    trading_sched.start()
    perform_analysis()


def save_dataframe_to_csv(df, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        print(f"DataFrame successfully saved to {file_path}")
    except Exception as e:
        print(f"Failed to save DataFrame to {file_path}: {e}")


def read_dataframe_from_csv(file_path):
    return pd.read_csv(file_path)
