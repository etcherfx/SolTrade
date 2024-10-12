import asyncio
import os
import pandas as pd
import requests
from tabulate import tabulate
from apscheduler.schedulers.background import BlockingScheduler

from soltrade.config import config
from soltrade.log import log_general, log_transaction
from soltrade.strategy import (
    strategy,
    calc_stoploss,
    calc_trailing_stoploss,
    calc_entry_price,
    calc_takeprofit,
)
from soltrade.transactions import perform_swap, market
from soltrade.wallet import find_balance

config_instance = config()
primary_mint = config_instance.primary_mint
primary_mint_symbol = config_instance.primary_mint_symbol
secondary_mint = config_instance.secondary_mint
secondary_mint_symbol = config_instance.secondary_mint_symbol
api_key = config_instance.api_key
trading_interval_minutes = config_instance.trading_interval_minutes
price_update_seconds = config_instance.price_update_seconds

market("data/position.csv")

initial_primary_balance = find_balance(primary_mint)
initial_secondary_balance = find_balance(secondary_mint)


def fetch_price(symbol):
    url = "https://min-api.cryptocompare.com/data/price"
    headers = {"authorization": api_key}
    params = {"fsym": symbol, "tsyms": "USD"}
    response = requests.get(url, headers=headers, params=params)
    price = response.json().get("USD", 0)
    return price


initial_primary_price = fetch_price(primary_mint_symbol)
initial_secondary_price = fetch_price(secondary_mint_symbol)


def fetch_candlestick() -> dict:
    url = "https://min-api.cryptocompare.com/data/v2/histominute"
    headers = {"authorization": api_key}
    params = {
        "tsym": primary_mint_symbol,
        "fsym": secondary_mint_symbol,
        "limit": 50,
        "aggregate": trading_interval_minutes,
    }
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()
    if response_json.get("Response") == "Error":
        log_general.error(response_json.get("Message"))
        exit()
    return response_json


def format_as_money(value):
    return "${:,.2f}".format(value)


def perform_analysis():
    os.system("cls" if os.name == "nt" else "clear")
    log_general.debug("Soltrade is analyzing the market; no trade has been executed.")
    market_instance = market()
    market_instance.load_position()
    candle_json = fetch_candlestick()
    candle_dict = candle_json["Data"]["Data"]
    columns = ["close", "high", "low", "open", "time"]
    new_df = pd.DataFrame(candle_dict, columns=columns)
    new_df["time"] = pd.to_datetime(new_df["time"], unit="s")
    new_df = strategy(new_df)
    new_df["total_profit"] = 0
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
        for col in [
            "entry_price",
            "takeprofit",
            "stoploss",
            "trailing_stoploss",
            "trailing_stoploss_target",
        ]:
            if col in df.columns:
                df[col] = df.iloc[0][col]
    except FileNotFoundError:
        df = new_df

    current_primary_balance = find_balance(primary_mint)
    current_secondary_balance = find_balance(secondary_mint)
    initial_total_value = (initial_primary_balance * initial_primary_price) + (
        initial_secondary_balance * initial_secondary_price
    )
    current_total_value = (
        current_primary_balance * fetch_price(primary_mint_symbol)
    ) + (current_secondary_balance * fetch_price(secondary_mint_symbol))
    total_profit = current_total_value - initial_total_value
    df["total_profit"] = total_profit
    df["total_profit"] = df["total_profit"].apply(format_as_money)

    df["position"] = "Open" if market_instance.position else "Closed"

    last_row = df.iloc[[-1]].drop(columns=["high", "low", "open", "time"])
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
        "takeprofit": "Take Profit",
        "trailing_stoploss": "Trailing Stoploss",
        "trailing_stoploss_target": "Trailing Stoploss Target",
        "total_profit": "Total Profit",
        "position": "Position",
    }
    last_row = last_row.rename(columns=custom_headers)
    print(tabulate(last_row.T, headers="keys", tablefmt="rounded_grid"))

    if not market_instance.position:
        handle_buy_signal(df, market_instance, data_file_path)
    else:
        handle_sell_signal(df, market_instance, data_file_path)


def handle_buy_signal(df, market_instance, data_file_path):
    input_amount = find_balance(primary_mint)
    if df["entry"].iat[-1] == 1:
        if input_amount <= 0:
            log_transaction.info(
                f"SolTrade has detected a buy signal, but does not have enough {primary_mint_symbol} to trade."
            )
            return
        log_transaction.info(
            f"SolTrade has detected a buy signal using {input_amount} {primary_mint_symbol}."
        )
        is_swapped = asyncio.run(perform_swap(input_amount, primary_mint))
        if is_swapped:
            df = calc_entry_price(df)
            df = calc_stoploss(df)
            df = calc_takeprofit(df)
            df = calc_trailing_stoploss(df)
            market_instance.update_position(
                True, df["stoploss"].iat[-1], df["takeprofit"].iat[-1]
            )
        save_dataframe_to_csv(df, data_file_path)


def handle_sell_signal(df, market_instance, data_file_path):
    input_amount = find_balance(secondary_mint)
    df = calc_trailing_stoploss(df)

    if df["exit"].iat[-1] == 1:
        log_transaction.info(
            f"SolTrade has detected a sell signal for {input_amount} {secondary_mint_symbol}."
        )
        asyncio.run(perform_swap(input_amount, secondary_mint))
        market_instance.update_position(False, 0, 0)
        df = df.drop(
            columns=[
                "stoploss",
                "entry_price",
                "trailing_stoploss",
                "trailing_stoploss_target",
                "takeprofit",
            ]
        )
        save_dataframe_to_csv(df, data_file_path)


def start_trading():
    log_general.info("Soltrade has now initialized the trading algorithm.")
    trading_sched = BlockingScheduler()
    trading_sched.add_job(
        perform_analysis, "interval", seconds=price_update_seconds, max_instances=1
    )
    trading_sched.start()


def save_dataframe_to_csv(df, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        print(f"DataFrame successfully saved to {file_path}")
    except Exception as e:
        print(f"Failed to save DataFrame to {file_path}: {e}")


def read_dataframe_from_csv(file_path):
    return pd.read_csv(file_path)
