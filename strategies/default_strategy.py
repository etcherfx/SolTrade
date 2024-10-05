import pandas_ta as ta
from soltrade.config import config
from soltrade.log import log_general
from .base_strategy import BaseStrategy


class DefaultStrategy(BaseStrategy):
    def apply_strategy(self):
        if config().strategy == "default":
            if config().strategy is None:
                log_general.info("No strategy selected in config.json using default")

            ### Populate default indicators:

            # Calculates EMA
            self.df["ema_s"] = ta.ema(self.df["close"], length=5)
            self.df["ema_m"] = ta.ema(self.df["close"], length=21)

            # Bollinger Bands
            sma = ta.sma(self.df["close"], length=14)
            std = self.df["close"].rolling(14).std()
            self.df["upper_bband"] = sma + std * 2
            self.df["lower_bband"] = sma - std * 2

            # RSI
            self.df["rsi"] = ta.rsi(self.df["close"], length=14)

            # Entry
            entry = (
                (self.df["ema_s"] > self.df["ema_m"])
                | (self.df["close"] < self.df["lower_bband"])
            ) & (self.df["rsi"] <= 31)
            self.df.loc[entry, "entry"] = 1

            # Exit
            exit = (
                (self.df["ema_s"] < self.df["ema_m"])
                | (self.df["close"] > self.df["upper_bband"])
            ) & (self.df["rsi"] >= 65)
            self.df.loc[exit, "exit"] = 1

        return self.df
