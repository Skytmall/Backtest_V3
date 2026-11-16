# core/engine.py
import math
from typing import Dict, Optional, List
import numpy as np
import pandas as pd

from core.models import BacktestConfig, Order, Position
from strategies.base import BaseStrategy
from core.metrics import evaluate_performance
from core.debug_logger import trace_call

class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.order_id_counter = 0

    def _calc_fee(self, gross_amount: float) -> float:
        fee = gross_amount * self.config.fee_rate
        enable_min = getattr(self.config, "enable_min_fee", True)
        min_fee = getattr(self.config, "min_fee", 20.0)
        if enable_min:
            fee = max(fee, min_fee)
        return fee

    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        if "VWAP" in df.columns:
            return df["VWAP"]
        elif "High" in df.columns and "Low" in df.columns and "Close" in df.columns:
            return (df["High"] + df["Low"] + df["Close"]) / 3.0
        else:
            return df["Close"]

    def _create_order(self, side: str, ref_price: float, qty: int, current_volume: float) -> Order:
        self.order_id_counter += 1
        if self.config.order_type == "limit":
            offset = self.config.limit_offset_pct
            price = ref_price * (1 + offset) if side == "BUY" else ref_price * (1 - offset)
        else:
            price = ref_price
            
        if self.config.max_volume_pct and current_volume > 0:
            volume_cap = math.floor(current_volume * self.config.max_volume_pct)
            qty = min(qty, volume_cap)
            
        if self.config.lot_size > 1:
            qty = (qty // self.config.lot_size) * self.config.lot_size

        return Order(order_id=self.order_id_counter, side=side, order_type=self.config.order_type, price=price, qty=qty)

    def _check_exit_conditions(self, strategy: BaseStrategy, df: pd.DataFrame, i: int, position: Position, curr_high: float, curr_low: float) -> tuple:
        entry_price = position.avg_cost
        highest_price = position.highest_price

        if self.config.stop_loss_pct is not None:
            if curr_low <= entry_price * (1.0 - self.config.stop_loss_pct):
                return True, f"固定停損 (-{self.config.stop_loss_pct:.1%})"

        if self.config.trailing_stop_pct is not None:
            if curr_low <= highest_price * (1.0 - self.config.trailing_stop_pct):
                return True, f"移動停損 (回檔 -{self.config.trailing_stop_pct:.1%})"

        if self.config.take_profit_pct is not None:
            if curr_high >= entry_price * (1.0 + self.config.take_profit_pct):
                return True, f"固定停利 (+{self.config.take_profit_pct:.1%})"

        if self.config.max_holding_days is not None:
            if position.max_holding_days >= self.config.max_holding_days:
                return True, f"時間停損 (達最大 {self.config.max_holding_days} 天)"

        strat_exit, strat_reason = strategy.check_exit_signal(df, i, {
            "avg_cost": entry_price, 
            "total_shares": position.total_shares,
            "highest_price": highest_price
        })
        if strat_exit:
            return True, strat_reason

        return False, ""

    @trace_call
    def run(self, df: pd.DataFrame, strategy: BaseStrategy, start_date: str = None, end_date: str = None) -> Dict:
        df_proc = df.copy().ffill().dropna(subset=["Open", "High", "Low", "Close"])
        df_proc = strategy.generate_indicators(df_proc)
        df_proc["VWAP_Calc"] = self._calculate_vwap(df_proc)

        if start_date or end_date:
            df_proc = df_proc.loc[start_date:end_date].copy()
        if len(df_proc) < 2: raise ValueError("資料過少")

        cash = self.config.initial_capital
        position = Position()
        equity_curve, trades_history = [], []
        pending_orders: List[Order] = []

        # 💡 新增：記帳變數
        total_fee = 0.0
        total_tax = 0.0

        open_arr, high_arr, low_arr = df_proc["Open"].values, df_proc["High"].values, df_proc["Low"].values
        close_arr, vwap_arr = df_proc["Close"].values, df_proc["VWAP_Calc"].values
        vol_arr = df_proc["Volume"].values if "Volume" in df_proc.columns else np.zeros(len(df_proc))
        dates = df_proc.index

        for i in range(len(df_proc) - 1):
            today_open, today_high, today_low, today_close = open_arr[i], high_arr[i], low_arr[i], close_arr[i]
            today_vol = vol_arr[i]

            position.update_bar(today_high)

            # ================= 1. 撮合掛單 =================
            for order in list(pending_orders):
                if order.status == "CANCELLED": continue
                
                fill_price = 0.0
                if order.order_type == "limit":
                    if order.side == "BUY" and today_low <= order.price:
                        fill_price = min(today_open, order.price)
                    elif order.side == "SELL" and today_high >= order.price:
                        fill_price = max(today_open, order.price)
                elif order.order_type == "market":
                    fill_price = today_open

                if fill_price > 0:
                    if order.side == "BUY":
                        gross = order.qty * fill_price
                        fee = self._calc_fee(gross)
                        cash -= (gross + fee)
                        total_fee += fee  # 💡 累加手續費
                        position.add_lot(order.qty, fill_price, dates[i].strftime('%Y-%m-%d'))
                    else:
                        removed_lots = position.remove_shares(order.qty)
                        for lot in removed_lots:
                            exit_gross = lot["shares"] * fill_price
                            exit_fee = self._calc_fee(exit_gross)
                            exit_tax = exit_gross * self.config.tax_rate
                            
                            total_fee += exit_fee  # 💡 累加手續費
                            total_tax += exit_tax  # 💡 累加稅金
                            
                            revenue = exit_gross - exit_fee - exit_tax
                            cash += revenue

                            entry_gross = lot["shares"] * lot["entry_price"]
                            entry_fee = self._calc_fee(entry_gross)
                            entry_cost = entry_gross + entry_fee
                            ret_calc = (revenue / entry_cost) - 1

                            trades_history.append({
                                "entry_date": lot["entry_date"], "entry_price": lot["entry_price"],
                                "exit_date": dates[i].strftime('%Y-%m-%d'), "exit_price": fill_price,
                                "shares": lot["shares"], "return": ret_calc,
                                "exit_reason": order.status
                            })
                    order.status = "FILLED"
                    pending_orders.remove(order)

            # ================= 2. 風控檢查 =================
            if position.total_shares > 0:
                exit_triggered, exit_reason = self._check_exit_conditions(strategy, df_proc, i, position, today_high, today_low)
                
                if exit_triggered:
                    sell_qty = strategy.get_exit_qty(df_proc, i, {"avg_cost": position.avg_cost}, position.total_shares)
                    
                    if sell_qty > 0:
                        sell_order = self._create_order("SELL", today_close, sell_qty, today_vol)
                        sell_order.status = exit_reason
                        if sell_order.qty > 0:
                            pending_orders.append(sell_order)
                    continue

            # ================= 3. 進場檢查 =================
            if strategy.check_entry_signal(df_proc, i):
                investable_cash = cash * self.config.position_pct
                target_qty = strategy.get_entry_qty(df_proc, i, today_close, investable_cash)

                if target_qty > 0:
                    # 💡 現金約束：考慮手續費（含最低手續費），逐步下修到現金夠為止
                    qty = target_qty
                    while qty > 0:
                        gross = qty * today_close
                        fee = self._calc_fee(gross)
                        if gross + fee <= cash:
                            break
                        qty -= 1
                    if qty > 0:
                        buy_order = self._create_order("BUY", today_close, qty, today_vol)
                        if buy_order.qty > 0:
                            pending_orders.append(buy_order)

            # ================= 4. 紀錄權益 =================
            current_equity = cash + position.total_shares * today_close
            equity_curve.append({"Date": dates[i], "Equity": current_equity})

        # ================= 5. 強制平倉與結算 =================
        last_close = close_arr[-1]
        if position.total_shares > 0:
            removed_lots = position.remove_shares(position.total_shares)
            for lot in removed_lots:
                exit_gross = lot["shares"] * last_close
                exit_fee = self._calc_fee(exit_gross)
                exit_tax = exit_gross * self.config.tax_rate
                
                total_fee += exit_fee  # 💡 累加手續費
                total_tax += exit_tax  # 💡 累加稅金
                
                revenue = exit_gross - exit_fee - exit_tax
                cash += revenue

                entry_gross = lot["shares"] * lot["entry_price"]
                entry_fee = self._calc_fee(entry_gross)
                entry_cost = entry_gross + entry_fee
                ret_calc = (revenue / entry_cost) - 1

                trades_history.append({
                    "entry_date": lot["entry_date"], "entry_price": lot["entry_price"],
                    "exit_date": dates[-1].strftime('%Y-%m-%d'), "exit_price": last_close,
                    "shares": lot["shares"], "return": ret_calc,
                    "exit_reason": "回測結束強制平倉"
                })
            position.clear()

        equity_curve.append({"Date": dates[-1], "Equity": cash})
        eq_df = pd.DataFrame(equity_curve).set_index("Date")
        
        # 💡 把統計結果塞進 metrics 回傳
        metrics = evaluate_performance(eq_df, trades_history, len(df_proc), self.config)
        metrics["Total_Fee"] = total_fee
        metrics["Total_Tax"] = total_tax

        return {
            "metrics": metrics,
            "equity_df": eq_df,
            "trades_df": pd.DataFrame(trades_history)
        }

    @trace_call
    def run_benchmark(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> Dict:
        df_proc = df.copy().ffill().dropna(subset=["Open", "High", "Low", "Close"])
        if start_date or end_date:
            df_proc = df_proc.loc[start_date:end_date].copy()
        if len(df_proc) < 2: raise ValueError("資料過少")

        dates = df_proc.index
        open_arr = df_proc["Open"].values
        close_arr = df_proc["Close"].values
        
        entry_price = open_arr[1]
        entry_date = dates[1]
        final_close = close_arr[-1]
        
        initial_cap = self.config.initial_capital
        final_eq = initial_cap * (final_close / entry_price)
        ret = (final_eq - initial_cap) / initial_cap
        
        trades_history = [{
            "entry_date": entry_date.strftime('%Y-%m-%d'), "entry_price": entry_price,
            "exit_date": dates[-1].strftime('%Y-%m-%d'), "exit_price": final_close,
            "shares": math.floor(initial_cap / entry_price), 
            "return": ret, "exit_reason": "純指數對照"
        }]

        equity_curve = [{"Date": d, "Equity": initial_cap * (c / entry_price)} for d, c in zip(dates[1:], close_arr[1:])]
        equity_curve.insert(0, {"Date": dates[0], "Equity": initial_cap})
        eq_df = pd.DataFrame(equity_curve).set_index("Date")
        
        return {
            "metrics": evaluate_performance(eq_df, trades_history, len(df_proc), self.config),
            "equity_df": eq_df,
            "trades_df": pd.DataFrame(trades_history)
        }

    def run_indicator_only(self, df: pd.DataFrame, strategy: BaseStrategy) -> pd.DataFrame:
        df_proc = df.copy().ffill().dropna(subset=["Open", "High", "Low", "Close"])
        return strategy.generate_indicators(df_proc)