import importlib
import pandas as pd
from soltrade.config import config
from soltrade.log import log_general

strategy_instance = None


def load_strategy_class(strategy_name):
    strategy_module = importlib.import_module(f"strategies.{strategy_name}_strategy")
    strategy_class = getattr(strategy_module, f"{strategy_name.capitalize()}Strategy")
    return strategy_class


def strategy(df: pd.DataFrame):
    global strategy_instance
    strategy_name = config().strategy or "default"
    try:
        StrategyClass = load_strategy_class(strategy_name)
        strategy_instance = StrategyClass(df)
        df = strategy_instance.apply_strategy()
    except (ModuleNotFoundError, AttributeError) as e:
        log_general.error(f"Strategy {strategy_name} not found: {e}")
        raise

    return df


def set_position(df, position):
    df["position"] = position
    return df


def calc_entry_price(df):
    entry_price = df["close"].iat[-1]
    df["entry_price"] = entry_price
    return df


def calc_stoploss(df):
    global strategy_instance
    sl = float(strategy_instance.stoploss)
    df["stoploss"] = df["close"].iat[-1] * (1 - (sl / 100))
    return df


def calc_takeprofit(df):
    global strategy_instance
    tp = float(strategy_instance.takeprofit)
    df["takeprofit"] = df["close"].iat[-1] * (1 + (tp / 100))
    return df


def calc_trailing_stoploss(df):
    global strategy_instance
    tsl = float(strategy_instance.trailing_stoploss)
    tslt = float(strategy_instance.trailing_stoploss_target)

    high_prices = df["high"]
    trailing_stop = []
    tracking_started = False
    highest_price = df["high"].iat[0]

    for price in high_prices:
        if not tracking_started and price >= df["entry_price"].iat[0] * (
            1 + tslt / 100
        ):
            tracking_started = True
            highest_price = price
        if tracking_started:
            if price > highest_price:
                highest_price = price
            stop_price = highest_price * (1 - tsl / 100)
            trailing_stop.append(stop_price)
        else:
            trailing_stop.append(None)

    df["trailing_stoploss"] = trailing_stop
    df["trailing_stoploss_target"] = df["entry_price"] * (1 + tslt / 100)

    return df
