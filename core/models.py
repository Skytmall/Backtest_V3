# src/core/models.py
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class BacktestConfig:
    initial_capital: float = 1000000.0
    fee_rate: float = 0.001425
    tax_rate: float = 0.003

    enable_min_fee: bool = True
    min_fee: float = 20.0
    position_pct: float = 1.0

    order_type: str = "market"
    exec_price_type: str = "next_open"
    limit_offset_pct: float = 0.0
    lot_size: int = 1000

    stop_loss_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_holding_days: Optional[int] = None

    risk_free_rate: float = 0.02
    enable_price_limit: bool = True
    price_limit_pct: float = 0.10
    max_volume_pct: Optional[float] = 0.10
    unfilled_action: str = "cancel"

    best_metric: str = "Sharpe_Ratio"
    ai_context_top_n: int = 5
    ai_context_pad: int = 10
    formatter_version: str = "1.0"


@dataclass
class Order:
    order_id: int
    side: str
    order_type: str
    price: float
    qty: int
    status: str = "PENDING"
    filled_qty: int = 0
    filled_price: float = 0.0


@dataclass
class Position:
    lots: List[Dict[str, Any]] = field(default_factory=list)
    highest_price: float = 0.0
    max_holding_days: int = 0

    @property
    def total_shares(self) -> int:
        return sum(lot["shares"] for lot in self.lots)

    @property
    def avg_cost(self) -> float:
        if not self.lots or self.total_shares == 0:
            return 0.0
        total_cost = sum(lot["shares"] * lot["entry_price"] for lot in self.lots)
        return total_cost / self.total_shares

    def add_lot(self, shares: int, price: float, date: str) -> None:
        if shares > 0:
            self.lots.append({
                "shares": shares,
                "entry_price": price,
                "entry_date": date,
                "holding_days": 0,
            })
            self.highest_price = max(self.highest_price, price)

    def remove_shares(self, qty: int) -> List[Dict]:
        removed_lots = []
        remaining = qty
        while remaining > 0 and self.lots:
            lot = self.lots[0]
            if lot["shares"] <= remaining:
                removed_lots.append(lot)
                remaining -= lot["shares"]
                self.lots.pop(0)
            else:
                split_lot = lot.copy()
                split_lot["shares"] = remaining
                removed_lots.append(split_lot)
                lot["shares"] -= remaining
                remaining = 0
        return removed_lots

    def clear(self) -> None:
        self.lots.clear()
        self.highest_price = 0.0
        self.max_holding_days = 0

    def update_bar(self, current_high: float) -> None:
        if self.total_shares > 0:
            self.highest_price = max(self.highest_price, current_high)
            self.max_holding_days += 1
            for lot in self.lots:
                lot["holding_days"] += 1