# src/core/worker.py
import traceback
from typing import Dict, Any, Optional
import pandas as pd

from core.models import BacktestConfig
from core.engine import BacktestEngine
from strategies.loader import load_all_strategies
from strategies.base import STRATEGY_REGISTRY


def run_single_task_worker(
    df: pd.DataFrame, 
    ticker: str, 
    strat_id: str, 
    params: Dict[str, Any], 
    config: BacktestConfig, 
    split_date: Optional[str] = None
) -> dict:
    """執行單一任務的回測（由 ThreadPoolExecutor 呼叫）。"""
    if strat_id not in STRATEGY_REGISTRY:
        load_all_strategies()

    try:
        strat_cls = STRATEGY_REGISTRY.get(strat_id)
        if not strat_cls: 
            raise ValueError(f"找不到策略: {strat_id}")
            
        strategy = strat_cls(**params)
        engine = BacktestEngine(config)

        result = {
            "ticker": ticker,
            "strat_id": strat_id,
            "params": params,
            "success": True,
            "error_msg": "",
            "is": {},
            "oos": {},
            "benchmark": {}
        }

        # 執行 IS (In-Sample)
        if split_date and split_date.strip():
            result["is"] = engine.run(df, strategy, end_date=split_date)
        else:
            result["is"] = engine.run(df, strategy)

        # 執行 OOS (Out-of-Sample)
        if split_date and split_date.strip():
            result["oos"] = engine.run(df, strategy, start_date=split_date)
            result["benchmark"]["is"] = engine.run_benchmark(df, end_date=split_date)
            result["benchmark"]["oos"] = engine.run_benchmark(df, start_date=split_date)
        else:
            result["benchmark"]["is"] = engine.run_benchmark(df)

        return result

    except Exception as e:
        return {
            "success": False, 
            "error_msg": str(e), 
            "ticker": ticker,
            "strat_id": strat_id,
            "params": params,
            "traceback": traceback.format_exc()
        }