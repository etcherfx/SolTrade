import asyncio
import json
from io import StringIO

import pandas as pd
import requests
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

market("position.json")


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


# Analyzes the current market variables and determines trades
def perform_analysis():
    log_general.debug("Soltrade is analyzing the market; no trade has been executed.")

    market_instance = market()
    market_instance.load_position()

    # Converts JSON response for DataFrame manipulation
    candle_json = fetch_candlestick()
    candle_dict = candle_json["Data"]["Data"]

    # Creates DataFrame for manipulation
    columns = ["close", "high", "low", "open", "time"]
    df = pd.DataFrame(candle_dict, columns=columns)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    cl = df["close"]
    df = strategy(df)
    data_file_path = "data.csv"
    print(df.tail(2))

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
                print(df.tail(2))
                takeprofit = cl.iat[-1] * 1.25
                market_instance.update_position(
                    True, df["stoploss"].iloc[-1], takeprofit
                )
            save_dataframe_to_csv(df, data_file_path)
            return

    else:
        # Read DataFrame from JSON file
        df = read_dataframe_from_csv(data_file_path)
        print(df.tail(2))
        input_amount = find_balance(secondary_mint)
        df = calc_trailing_stoploss(df)
        stoploss = df["stoploss"].iloc[-1]
        trailing_stoploss = df["trailing_stoploss"].iloc[-1]

        # Check Stoploss
        if df["close"].iloc[-1] <= stoploss:
            log_transaction.info(
                f"Soltrade has detected a sell signal for {input_amount} ${secondary_mint_symbol}. Stoploss has been reached."
            )
            asyncio.run(perform_swap(input_amount, secondary_mint))
            stoploss = takeprofit = 0
            df["entry_price"] = None

        # Check Trailing Stoploss
        elif trailing_stoploss is not None and df["close"].iloc[-1] < trailing_stoploss:
            log_transaction.info(
                f"Soltrade has detected a sell signal for {input_amount} ${secondary_mint_symbol}. Trailing stoploss has been reached."
            )
            asyncio.run(perform_swap(input_amount, secondary_mint))
            stoploss = takeprofit = 0
            df["entry_price"] = None

        # Check Strategy
        elif df["exit"].iloc[-1] == 1:
            log_transaction.info(
                f"Soltrade has detected a sell signal for {input_amount} ${secondary_mint_symbol}."
            )
            asyncio.run(perform_swap(input_amount, secondary_mint))
            stoploss = takeprofit = 0
            df["entry_price"] = None

        save_dataframe_to_csv(df, data_file_path)


# This starts the trading function on a timer
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


# Function to save DataFrame to CSV file
def save_dataframe_to_csv(df, file_path):
    df.to_csv(file_path, index=False)


# Function to read DataFrame from CSV file
def read_dataframe_from_csv(file_path):
    return pd.read_csv(file_path)
