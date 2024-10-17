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
    set_position,
)
from soltrade.transactions import perform_swap
from soltrade.wallet import find_balance

config_instance = config()
primary_mint = config_instance.primary_mint
primary_mint_symbol = config_instance.primary_mint_symbol
secondary_mints = config_instance.secondary_mints
secondary_mint_symbols = config_instance.secondary_mint_symbols
api_key = config_instance.api_key
trading_interval_minutes = config_instance.trading_interval_minutes
price_update_seconds = config_instance.price_update_seconds

initial_primary_balance = find_balance(primary_mint)
initial_secondary_balances = [find_balance(mint) for mint in secondary_mints]


def fetch_price(symbol):
    url = "https://min-api.cryptocompare.com/data/price"
    headers = {"authorization": api_key}
    params = {"fsym": symbol, "tsyms": "USD"}
    response = requests.get(url, headers=headers, params=params)
    price = response.json().get("USD", 0)
    return price


initial_primary_price = fetch_price(primary_mint_symbol)
initial_secondary_prices = [fetch_price(symbol) for symbol in secondary_mint_symbols]


def fetch_candlestick(primary_mint_symbol, secondary_mint_symbol) -> dict:
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
    data_frames = []

    for secondary_mint, secondary_mint_symbol in zip(
        secondary_mints, secondary_mint_symbols
    ):
        candle_json = fetch_candlestick(primary_mint_symbol, secondary_mint_symbol)
        candle_dict = candle_json["Data"]["Data"]
        columns = ["close", "high", "low", "open", "time"]
        new_df = pd.DataFrame(candle_dict, columns=columns)
        new_df["time"] = pd.to_datetime(new_df["time"], unit="s")
        new_df = strategy(new_df)
        new_df["total_profit"] = 0
        new_df["mint"] = secondary_mint_symbol
        new_df["position"] = False
        data_file_path = f"data/{secondary_mint_symbol}_data.csv"

        try:
            existing_df = read_dataframe_from_csv(data_file_path)
            if existing_df["position"].iat[-1]:
                columns_to_merge = [
                    "position",
                    "entry_price",
                    "takeprofit",
                    "stoploss",
                    "trailing_stoploss",
                    "trailing_stoploss_target",
                ]

                for col in columns_to_merge:
                    new_df[col] = existing_df.iloc[-1][col]

            df = new_df
        except FileNotFoundError:
            df = new_df

        data_frames.append(df)

    combined_df = pd.concat(data_frames, axis=0)
    combined_df.drop_duplicates(subset=["time", "mint"], keep="last", inplace=True)

    current_primary_balance = find_balance(primary_mint)
    current_secondary_balances = [find_balance(mint) for mint in secondary_mints]
    initial_total_value = (initial_primary_balance * initial_primary_price) + sum(
        initial_secondary_balance * initial_secondary_price
        for initial_secondary_balance, initial_secondary_price in zip(
            initial_secondary_balances, initial_secondary_prices
        )
    )
    current_total_value = (
        current_primary_balance * fetch_price(primary_mint_symbol)
    ) + sum(
        current_secondary_balance * fetch_price(secondary_mint_symbol)
        for current_secondary_balance, secondary_mint_symbol in zip(
            current_secondary_balances, secondary_mint_symbols
        )
    )
    total_profit = current_total_value - initial_total_value

    last_rows = combined_df.groupby("mint").tail(1)

    pivot_columns = [
        "close",
        "ema_s",
        "ema_m",
        "upper_bband",
        "lower_bband",
        "rsi",
        "entry",
        "exit",
        "entry_price",
        "stoploss",
        "takeprofit",
        "trailing_stoploss",
        "trailing_stoploss_target",
        "position",
    ]

    pivot_columns = [col for col in pivot_columns if col in last_rows.columns]
    last_rows_pivoted = last_rows.pivot(
        index="mint", columns="time", values=pivot_columns
    )
    last_rows_pivoted.columns = [f"{col[0]}" for col in last_rows_pivoted.columns]
    last_rows_pivoted = last_rows_pivoted.T

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
        "position": "Position",
    }
    last_rows_pivoted.rename(index=custom_headers, inplace=True)

    last_rows_pivoted.loc["Price"] = last_rows_pivoted.loc["Price"].apply(
        format_as_money
    )

    print(tabulate(last_rows_pivoted, headers="keys", tablefmt="rounded_grid"))

    profit_df = pd.DataFrame(
        {"Total Profit": [format_as_money(total_profit)]},
    )

    print(tabulate(profit_df, headers="keys", tablefmt="rounded_grid"))

    for df, secondary_mint, secondary_mint_symbol in zip(
        data_frames, secondary_mints, secondary_mint_symbols
    ):
        data_file_path = f"data/{secondary_mint_symbol}_data.csv"
        if not df["position"].iat[-1]:
            if handle_buy_signal(
                df, secondary_mint, data_file_path, secondary_mint_symbol
            ):
                break
        else:
            if handle_sell_signal(
                df, secondary_mint, data_file_path, secondary_mint_symbol
            ):
                break


def handle_buy_signal(df, secondary_mint, data_file_path, secondary_mint_symbol):
    input_amount = find_balance(primary_mint)
    if df["entry"].iat[-1] == 1:
        mint_symbol = df["mint"].iat[0]
        if input_amount <= 0:
            log_transaction.info(
                f"SolTrade has detected a buy signal, but does not have enough {primary_mint_symbol} to trade."
            )
            return False
        log_transaction.info(
            f"SolTrade has detected a buy signal for {mint_symbol} using {input_amount} {primary_mint_symbol}."
        )
        is_swapped = asyncio.run(
            perform_swap(
                input_amount,
                primary_mint,
                secondary_mint,
                primary_mint_symbol,
                secondary_mint_symbol,
            )
        )
        if is_swapped:
            df = calc_entry_price(df)
            df = calc_stoploss(df)
            df = calc_takeprofit(df)
            df = calc_trailing_stoploss(df)
            df = set_position(df, True)
            save_dataframe_to_csv(df, data_file_path)
            return True
        return False
    return False


def handle_sell_signal(df, secondary_mint, data_file_path, secondary_mint_symbol):
    input_amount = find_balance(secondary_mint)
    df = calc_trailing_stoploss(df)

    if df["exit"].iat[-1] == 1:
        mint_symbol = df["mint"].iat[0]
        log_transaction.info(
            f"SolTrade has detected a sell signal for {input_amount} {mint_symbol}."
        )
        is_swapped = asyncio.run(
            perform_swap(
                input_amount,
                secondary_mint,
                primary_mint,
                secondary_mint_symbol,
                primary_mint_symbol,
            )
        )
        if is_swapped:
            df = set_position(df, False)
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
            return True
        return False
    return False


def start_trading():
    log_general.info("Soltrade has now initialized the trading algorithm.")
    trading_sched = BlockingScheduler()
    trading_sched.add_job(
        perform_analysis, "interval", seconds=price_update_seconds, max_instances=1
    )
    perform_analysis()
    trading_sched.start()


def save_dataframe_to_csv(df, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        log_general.info(f"Data successfully saved to {file_path}")
    except Exception as e:
        log_general.error(f"Failed to save data to {file_path}: {e}")


def read_dataframe_from_csv(file_path):
    return pd.read_csv(file_path)
