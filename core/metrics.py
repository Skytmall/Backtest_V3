# core/metrics.py
import pandas as pd
import numpy as np
from typing import Dict, List
from core.models import BacktestConfig

def evaluate_performance(eq_df: pd.DataFrame, trades: List[Dict], total_bars: int, config: BacktestConfig) -> Dict:
    """計算基礎與進階績效指標"""
    if eq_df.empty: return {}

    total_years = total_bars / 252.0 if total_bars > 0 else 1.0
    final_eq = eq_df["Equity"].iloc[-1]
    total_return = (final_eq / config.initial_capital) - 1.0

    cagr = ((final_eq / config.initial_capital) ** (1.0 / total_years) - 1.0) if total_years > 0 else 0

    daily_returns = eq_df["Equity"].pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252)

    sharpe = (cagr - config.risk_free_rate) / volatility if volatility > 0 else 0

    downside_returns = daily_returns[daily_returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252)
    sortino = (cagr - config.risk_free_rate) / downside_std if downside_std > 0 else 0

    cummax = eq_df["Equity"].cummax()
    drawdown = (eq_df["Equity"] - cummax) / cummax
    mdd = drawdown.min()
    
    calmar = cagr / abs(mdd) if mdd != 0 else 0

    num_trades = len(trades)
    if num_trades > 0:
        win_trades = [t for t in trades if t["return"] > 0]
        loss_trades = [t for t in trades if t["return"] <= 0]
        win_rate = len(win_trades) / num_trades
        
        gross_profit = sum(t["return"] for t in win_trades)
        gross_loss = abs(sum(t["return"] for t in loss_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = gross_profit / len(win_trades) if win_trades else 0
        avg_loss = gross_loss / len(loss_trades) if loss_trades else 0
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_win, avg_loss = 0.0, 0.0

    avg_trade_return = float(np.mean([t["return"] for t in trades])) if num_trades > 0 else 0.0
    
    # 💡 新增：交易密集度 (每年交易幾次)
    trade_frequency = num_trades / total_years if total_years > 0 else 0

    return {
        "Total_Return": total_return,
        "CAGR": cagr,
        "Volatility": volatility,
        "Sharpe_Ratio": sharpe,
        "Sortino_Ratio": sortino,
        "Calmar_Ratio": calmar,
        "Max_Drawdown": mdd,
        "Total_Trades": num_trades,
        "Win_Rate": win_rate,
        "Profit_Factor": profit_factor,
        "Avg_Trade_Return": avg_trade_return,
        "Avg_Win": avg_win,
        "Avg_Loss": avg_loss,
        "Trade_Frequency": trade_frequency  # 💡 新增
    }

def calc_yearly_metrics(eq_df: pd.DataFrame, initial_cap: float) -> Dict[str, Dict[str, float]]:
    if eq_df.empty: return {}
    df = eq_df.copy()
    df.index = pd.to_datetime(df.index)
    yearly_last = df["Equity"].resample('YE').last().dropna()
    
    yearly_metrics = {}
    prev_equity = initial_cap
    for date, current_equity in yearly_last.items():
        year = str(date.year)
        ret = (current_equity - prev_equity) / prev_equity
        yearly_metrics[year] = {"Total_Return": ret, "End_Equity": current_equity}
        prev_equity = current_equity
    return yearly_metrics