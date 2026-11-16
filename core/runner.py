# src/core/runner.py
import itertools
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
import pandas as pd

from core.models import BacktestConfig
from core.worker import run_single_task_worker


def run_multi_stock_grid_search(
    df_dict: Dict[str, pd.DataFrame], 
    strat_id: str, 
    param_grid: Dict[str, List[Any]], 
    config: BacktestConfig, 
    split_date: Optional[str] = None, 
    max_workers: int = 4, 
    progress_callback: Optional[Callable[[int, int, List[dict]], None]] = None
) -> List[dict]:
    """舊版單策略多股票掃描（保留相容性）。"""
    keys = list(param_grid.keys())
    combos = [dict(zip(keys, v)) for v in itertools.product(*param_grid.values())]
    
    tasks = []
    for ticker, df in df_dict.items():
        for combo in combos:
            tasks.append((ticker, df, combo))
            
    total = len(tasks)
    if total == 0: return []
        
    results = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(run_single_task_worker, df, ticker, strat_id, combo, config, split_date): (ticker, combo)
            for (ticker, df, combo) in tasks
        }
        
        for future in as_completed(future_to_task):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                t, c = future_to_task[future]
                results.append({
                    "success": False,
                    "error_msg": f"任務執行失敗: {e}",
                    "ticker": t,
                    "params": c
                })
            completed += 1
            if progress_callback:
                progress_callback(completed, total, results)
                
    return results


def run_multi_strategy_multi_stock(
    df_dict: Dict[str, pd.DataFrame],
    strategy_grids: Dict[str, Dict[str, List[Any]]],
    config: BacktestConfig,
    split_date: Optional[str] = None,
    max_workers: int = 4,
    progress_callback: Optional[Callable[[int, int, List[dict]], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> List[dict]:
    """多策略 × 多股票 × 多參數的網格回測。"""
    tasks = []
    for strat_id, param_grid in strategy_grids.items():
        if not param_grid:
            continue
        keys = list(param_grid.keys())
        combos = [dict(zip(keys, v)) for v in itertools.product(*param_grid.values())]
        for ticker, df in df_dict.items():
            for combo in combos:
                tasks.append((ticker, df, strat_id, combo))
                
    total = len(tasks)
    if total == 0:
        return []
        
    results = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {}
        for ticker, df, strat_id, combo in tasks:
            future = executor.submit(
                run_single_task_worker, 
                df, ticker, strat_id, combo, config, split_date
            )
            future_to_task[future] = (ticker, strat_id, combo)
            
        for future in as_completed(future_to_task):
            if cancel_event is not None and cancel_event.is_set():
                for f in future_to_task:
                    f.cancel()
                break
                
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                t, s, c = future_to_task[future]
                results.append({
                    "success": False,
                    "error_msg": f"任務執行失敗: {e}",
                    "ticker": t,
                    "strat_id": s,
                    "params": c
                })
                
            completed += 1
            if progress_callback:
                progress_callback(completed, total, results)
                
    return results