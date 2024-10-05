import pandas as pd


class BaseStrategy:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def apply_strategy(self):
        raise NotImplementedError("Strategy must implement the apply_strategy method")
