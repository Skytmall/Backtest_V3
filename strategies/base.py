# strategies/base.py
from abc import ABC, abstractmethod
from typing import Dict, Tuple, Type
import pandas as pd
import math

STRATEGY_REGISTRY: Dict[str, Type['BaseStrategy']] = {}

class BaseStrategy(ABC):
    NAME = "BaseStrategy"
    DESCRIPTION = "基礎策略"
    PARAM_SCHEMA = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ != "BaseStrategy":
            if not cls.NAME or cls.NAME == "BaseStrategy":
                cls.NAME = cls.__name__
            STRATEGY_REGISTRY[cls.NAME] = cls

    @abstractmethod
    def generate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def check_entry_signal(self, df: pd.DataFrame, idx: int) -> bool:
        pass

    @abstractmethod
    def check_exit_signal(self, df: pd.DataFrame, idx: int, trade_info: Dict) -> Tuple[bool, str]:
        pass

    # 💡 全新介面：讓策略決定買多少、賣多少
    def get_entry_qty(self, df: pd.DataFrame, idx: int, current_price: float, available_cash: float) -> int:
        """預設：用可用資金全倉買入"""
        # 粗估手續費，避免超買
        max_shares = math.floor(available_cash / (current_price * 1.001425))
        return int(max_shares)

    def get_exit_qty(self, df: pd.DataFrame, idx: int, trade_info: Dict, total_shares: int) -> int:
        """預設：全部平倉"""
        return total_shares