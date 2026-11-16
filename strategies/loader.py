# strategies/loader.py
import os
import importlib.util
import inspect
import traceback
from strategies.base import BaseStrategy, STRATEGY_REGISTRY
from core.debug_logger import trace_call

@trace_call
def load_all_strategies():
    # 取得 strategies 資料夾的絕對路徑
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 走訪 strategies 底下所有的子資料夾與檔案
    for root, dirs, files in os.walk(base_dir):
        # 略過 __pycache__
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if not file.endswith(".py"):
                continue
                
            # 略過基礎類別、載入器和 __init__
            if file in ("base.py", "loader.py", "__init__.py"):
                continue
                
            file_path = os.path.join(root, file)
            
            # 計算相對於 strategies 的模組路徑 (例如: trend.ma_strategy)
            rel_path = os.path.relpath(file_path, base_dir)
            module_name = rel_path.replace(os.sep, ".")[:-3] # 去掉 .py
            
            try:
                # 使用動態載入，不依賴套件路徑
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception:
                print(f"❌ 載入模組 [{module_name}] 失敗：")
                traceback.print_exc()

    print(f"✅ 策略掃描完成，共載入 {len(STRATEGY_REGISTRY)} 個策略：")
    for key in STRATEGY_REGISTRY.keys():
        print(f" - {key}")