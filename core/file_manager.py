# core/file_manager.py
import pickle
import json
import os
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from core.models import BacktestResponse, BacktestConfig

class FileManager:
    """負責處理所有檔案讀寫、專案存檔與匯入"""

    # ================= 匯出 (Export) =================

    @staticmethod
    def export_to_csv(df: pd.DataFrame, filepath: str):
        """通用的 DataFrame 匯出 (交易明細、指標皆可用)"""
        if df.empty:
            raise ValueError("沒有資料可以匯出。")
        df.to_csv(filepath, index=True, encoding='utf-8-sig')

    @staticmethod
    def save_project(results: List[BacktestResponse], config: BacktestConfig, filepath: str):
        """將整個專案存成 Pickle"""
        project_data = {
            "version": "3.0",
            "config": config,
            "results": results
        }
        with open(filepath, "wb") as f:
            pickle.dump(project_data, f)

    # ================= 匯入 (Import) =================

    @staticmethod
    def load_project(filepath: str) -> Tuple[List[BacktestResponse], BacktestConfig]:
        """讀取專案 Pickle，並進行版本與格式驗證"""
        if not os.path.exists(filepath):
            raise FileNotFoundError("找不到指定的專案檔案。")
            
        try:
            with open(filepath, "rb") as f:
                data = pickle.load(f)
                
            # 版本防呆
            if data.get("version") != "3.0":
                raise ValueError(f"版本不相容！當前系統為 3.0，檔案版本為 {data.get('version')}")
                
            return data.get("results", []), data.get("config", BacktestConfig())
        except Exception as e:
            raise RuntimeError(f"載入專案失敗，檔案可能已損毀：{e}")

    @staticmethod
    def load_custom_data(filepath: str) -> pd.DataFrame:
        """
        匯入外部自訂 CSV 資料。
        必須包含 Date, Open, High, Low, Close, Volume 欄位。
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError("找不到指定的 CSV 檔案。")
            
        try:
            df = pd.read_csv(filepath)
            
            # 尋找日期欄位並設為 Index
            date_cols = ['Date', 'date', 'Datetime', '時間', '日期']
            found_date = next((col for col in date_cols if col in df.columns), None)
            
            if not found_date:
                raise ValueError("CSV 檔案中找不到日期欄位 (Date/日期)。")
                
            df[found_date] = pd.to_datetime(df[found_date])
            df.set_index(found_date, inplace=True)
            df.sort_index(inplace=True)
            
            # 統一欄位名稱 (首字大寫)
            df.columns = [str(c).capitalize() for c in df.columns]
            
            # 檢查必要欄位
            required = ["Open", "High", "Low", "Close"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"CSV 缺少必要欄位: {missing}")
                
            # 如果沒有 Volume，補 0 (避免引擎報錯)
            if "Volume" not in df.columns:
                df["Volume"] = 0.0
                
            return df.ffill().dropna(subset=required)
            
        except Exception as e:
            raise RuntimeError(f"讀取自訂資料失敗：{e}")

    @staticmethod
    def load_env_template(filepath: str) -> Dict[str, Any]:
        """讀取 JSON 環境模板參數"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"讀取環境模板失敗：{e}")