# src/ui/chart.py
import json
import pandas as pd
from core.paths import SRC_DIR

def safe_json(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    s = s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return s

def generate_candle_html(df_proc: pd.DataFrame, trades_df: pd.DataFrame, title: str) -> str:
    """直接生成 Lightweight Charts (v5.3.0) 的完整 HTML 字串。"""
    
    # 確保時間是遞增排序
    df_proc = df_proc.sort_index()

    # 1. K 線資料
    candle_data = []
    for date, row in df_proc.iterrows():
        candle_data.append({
            "time": date.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"])
        })
        
    # 2. 交易標記
    markers = []
    if trades_df is not None and not trades_df.empty:
        for _, row in trades_df.iterrows():
            markers.append({
                "time": pd.to_datetime(row["entry_date"]).strftime("%Y-%m-%d"),
                "position": "belowBar",
                "color": "#00e676",
                "shape": "arrowUp",
                "text": "進場"
            })
            markers.append({
                "time": pd.to_datetime(row["exit_date"]).strftime("%Y-%m-%d"),
                "position": "aboveBar",
                "color": "#ff1744",
                "shape": "arrowDown",
                "text": "出場"
            })
        markers.sort(key=lambda x: x["time"])

    json_candles = safe_json(candle_data)
    json_markers = safe_json(markers)

    # 💡 終極解法：直接讀取本地 JS 檔案內容並內嵌，避開所有路徑問題
    js_file_path = SRC_DIR / "ui" / "lightweight-charts..js"
    
    # 如果你的檔名沒有兩個點，請改成 "lightweight-charts.js"
    if not js_file_path.exists():
        js_file_path = SRC_DIR / "ui" / "lightweight-charts.js"

    try:
        with open(js_file_path, "r", encoding="utf-8") as f:
            js_library_content = f.read()
    except Exception as e:
        return f"<h2 style='color:red; padding:20px;'>讀取本地 JS 檔案失敗，請確認 {js_file_path} 存在。<br>{e}</h2>"

    # 3. 生成 HTML (嚴格基於 v5.3.0 語法)
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script>
        window.onerror = function(msg, url, line) {{
            document.body.innerHTML = '<div style="color:red; font-family:sans-serif; padding:20px;"><h2>JS 錯誤！</h2><p>' + msg + '</p></div>';
            return false;
        }};
    </script>
    <script>
        {js_library_content}
    </script>
    <style>
        body {{ margin: 0; padding: 0; background: #0e1117; }}
        #chart {{ width: 100vw; height: 100vh; }}
    </style>
</head>
<body>
    <div id="chart"></div>
    <script>
        if (typeof LightweightCharts === 'undefined') {{
            document.body.innerHTML = '<h2 style="color:#ff9800; font-family:sans-serif; padding:20px;">找不到 LightweightCharts 物件，請確認 JS 檔案是否正確。</h2>';
        }} else {{
            try {{
                var chart = LightweightCharts.createChart(document.getElementById('chart'), {{
                    layout: {{ background: {{ color: '#0e1117' }}, textColor: '#d1d4dc' }},
                    grid: {{ vertLines: {{ color: '#2B2B43' }}, horzLines: {{ color: '#2B2B43' }} }},
                    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                    rightPriceScale: {{ borderColor: '#2B2B43' }},
                    timeScale: {{ borderColor: '#2B2B43' }},
                    width: document.getElementById('chart').clientWidth,
                    height: document.getElementById('chart').clientHeight
                }});

                // 💡 v5 版本的正確語法：addSeries
                var candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {{
                    upColor: '#ef5350', 
                    downColor: '#26a69a', 
                    borderVisible: false,
                    wickUpColor: '#ef5350', 
                    wickDownColor: '#26a69a',
                }});

                var data = {json_candles};
                if (data.length > 0) {{
                    candleSeries.setData(data);
                }}
                
                var markers = {json_markers};
                if (markers.length > 0) {{
                    // 💡 v5 版本的正確語法：createSeriesMarkers
                    LightweightCharts.createSeriesMarkers(candleSeries, markers);
                }}
                
                chart.timeScale().fitContent();
            }} catch (e) {{
                document.body.innerHTML = '<div style="color:red; font-family:sans-serif; padding:20px;"><h2>畫圖時發生錯誤！</h2><p>' + e.message + '</p></div>';
            }}
        }}
    </script>
</body>
</html>"""