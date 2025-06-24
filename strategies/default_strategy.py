import talib as ta
from soltrade.config import config
from soltrade.log import log_general
from .base_strategy import BaseStrategy
import pandas as pd


class DefaultStrategy(BaseStrategy):
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.stoploss = 5
        self.takeprofit = 10
        self.trailing_stoploss = 2
        self.trailing_stoploss_target = 5

    def apply_strategy(self):
        if config().strategy == "default":
            ### Populate default indicators:

            # Calculates EMA
            self.df["ema_s"] = ta.EMA(self.df["close"], timeperiod=5)
            self.df["ema_m"] = ta.EMA(self.df["close"], timeperiod=21)

            # Bollinger Bands
            sma = ta.SMA(self.df["close"], timeperiod=14)
            std = self.df["close"].rolling(14).std()
            self.df["upper_bband"] = sma + std * 2
            self.df["lower_bband"] = sma - std * 2

            # RSI
            self.df["rsi"] = ta.RSI(self.df["close"], timeperiod=14)

            # Entry
            entry = (
                (self.df["ema_s"] > self.df["ema_m"])
                | (self.df["close"] < self.df["lower_bband"])
            ) & (self.df["rsi"] <= 30)
            self.df.loc[entry, "entry"] = 1

            # Exit
            exit = (
                (self.df["ema_s"] < self.df["ema_m"])
                | (self.df["close"] > self.df["upper_bband"])
            ) & (self.df["rsi"] >= 70)

            if "takeprofit" in self.df.columns:
                exit |= self.df["close"] >= self.df["takeprofit"]

            if "stoploss" in self.df.columns:
                exit |= self.df["close"] <= self.df["stoploss"]

            if "trailing_stoploss" in self.df.columns:
                exit |= self.df["close"] <= self.df["trailing_stoploss"]

            self.df.loc[exit, "exit"] = 1

        return self.df
