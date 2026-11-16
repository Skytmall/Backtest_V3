import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from core.models import BacktestConfig
from core.runner import run_multi_strategy_multi_stock
from data.fetcher import DataFetcher
from strategies.loader import load_all_strategies

def run_test():
    load_all_strategies()
    
    # 1. 抓取測試資料 (台積電)
    ticker = "2330.TW"
    print(f"下載 {ticker} 資料...")
    df = DataFetcher.get_data(ticker, "2022-01-01", "2023-01-01")
    df_dict = {ticker: df}
    
    # 2. 設定後端參數（完全對應截圖的需求）
    config = BacktestConfig(
        initial_capital=1000000,
        fee_rate=0.001425,
        enable_min_fee=True,
        min_fee=20.0,
        tax_rate=0.003,
        
        # 💡 交易單位：設為 1 代表允許「零股交易」！(原本是 1000)
        lot_size=1, 
        
        # 💡 進階風控：全部打開測試
        stop_loss_pct=0.08,        # 8% 停損
        trailing_stop_pct=0.10,    # 10% 移動停損
        take_profit_pct=0.20,      # 20% 停利
        max_holding_days=60,       # 最多持股 60 天
        
        # 漲跌停與吃單限制
        enable_price_limit=True,
        price_limit_pct=0.10,
        max_volume_pct=0.05        # 每次最多吃當天成交量的 5%
    )
    
    # 3. 設定策略與參數網格
    strategy_grids = {
        "KD_S1_黃金死亡交叉": {
            "period": [9],
            "k_smooth": [3],
            "d_smooth": [3]
        }
    }
    
    print("開始後端回測...")
    results = run_multi_strategy_multi_stock(
        df_dict=df_dict,
        strategy_grids=strategy_grids,
        config=config,
        max_workers=1
    )
    
    # 4. 顯示結果
    for r in results:
        if r.get("success"):
            metrics = r["is"]["metrics"]
            trades = r["is"]["trades_df"]
            print("\n✅ 回測成功！")
            print(f"總報酬: {metrics['Total_Return']:.2%}")
            print(f"總交易次數: {metrics['Total_Trades']} 次")
            
            print("\n📊 交易明細前 5 筆 (驗證是否為零股)：")
            if not trades.empty:
                print(trades[["entry_date", "entry_price", "shares", "return", "exit_reason"]].head())
                print(f"\n👉 注意看 shares 欄位，不再是 1000 的倍數，而是精確的股數！")
                print(f"👉 注意看 exit_reason，應該會看到觸發停損/停利/時間停損的字眼。")
        else:
            print("❌ 回測失敗:", r.get("error_msg"))

if __name__ == "__main__":
    run_test()