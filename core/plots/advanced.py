# src/core/plots/advanced.py
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from sklearn.linear_model import LinearRegression

pio.templates.default = "plotly_dark"

def _wrap_html(fig, title: str) -> str:
    fig.update_layout(title=title, margin=dict(l=40, r=40, t=50, b=40), height=650)
    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f"<html><body style='margin:0; padding:10px; background:#0e1117;'>{html}</body></html>"

def generate_advanced_chart(results: list, metric_key: str, chart_type: str, metric_zh: str) -> str:
    """根據 V2 邏輯重構的進階圖表產生器 (純後端)。"""
    if not results:
        return "<h2 style='color:white;'>無數據</h2>"

    # 1. 處理多股票：預設選取第一支有結果的股票，避免迴歸失真
    available_tickers = list(set([r.get("ticker", "未指定") for r in results if r.get("success")]))
    if not available_tickers:
        return "<h2 style='color:white;'>無有效結果</h2>"
    
    selected_ticker = available_tickers[0]
    filtered_res = [r for r in results if r.get("ticker") == selected_ticker and r.get("success")]

    if not filtered_res:
        return "<h2 style='color:white;'>無數據</h2>"

    # 2. 建立 DataFrame
    data = []
    for r in filtered_res:
        row = r["params"].copy()
        row["metric"] = r["is"].get("metrics", {}).get(metric_key, 0)
        data.append(row)
    df = pd.DataFrame(data)

    # 找出變動的參數
    param_cols = [c for c in df.columns if c != "metric"]
    varying_params = [c for c in param_cols if df[c].nunique() > 1]
    
    if not varying_params:
        return "<h2 style='color:orange;'>該股票沒有變動的參數，無法進行分析。</h2>"

    # 3. 根據圖表類型繪圖
    fig = go.Figure()
    title = f"{selected_ticker} - {metric_zh} 分析"

    if chart_type == "一維敏感度 (散點+折線)":
        x_col = varying_params[0]
        df_mean = df.groupby(x_col)["metric"].mean().reset_index()
        
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df["metric"], mode='markers',
            marker=dict(color='rgba(100, 181, 246, 0.4)', size=8, line=dict(width=1, color='rgba(255,255,255,0.5)')),
            name='單次回測結果'
        ))
        fig.add_trace(go.Scatter(
            x=df_mean[x_col], y=df_mean["metric"], mode='lines+markers',
            line=dict(color='#ff9800', width=3), marker=dict(size=8, color='#ff9800'),
            name='平均趨勢'
        ))
        fig.update_layout(xaxis_title=x_col, yaxis_title=metric_zh, hovermode="closest")
        return _wrap_html(fig, f"{x_col} 對 {metric_zh} 的敏感度")

    elif chart_type == "箱型圖 (穩定度)":
        x_col = varying_params[0]
        fig = px.box(df, x=x_col, y="metric", color=x_col, points="all", labels={"metric": metric_zh})
        return _wrap_html(fig, f"{x_col} 的績效穩定度")

    elif chart_type == "熱力圖 (2參數)":
        if len(varying_params) >= 2:
            px_param, py_param = varying_params[0], varying_params[1]
            pivot_df = df.groupby([px_param, py_param])["metric"].mean().reset_index()
            fig = px.density_heatmap(pivot_df, x=px_param, y=py_param, z="metric", histfunc="avg", text_auto=".2f", color_continuous_scale="RdYlGn", labels={"metric": metric_zh})
            return _wrap_html(fig, f"{px_param} vs {py_param} 熱力圖")
        return "<h2 style='color:orange;'>需要至少 2 個變動參數才能畫熱力圖</h2>"

    elif chart_type == "3D 散佈圖 (3參數)":
        if len(varying_params) >= 3:
            x, y, z = varying_params[0], varying_params[1], varying_params[2]
            fig = px.scatter_3d(df, x=x, y=y, z=z, color="metric", color_continuous_scale="RdYlGn", opacity=0.8, labels={"metric": metric_zh})
            return _wrap_html(fig, f"3D 參數空間分析")
        return "<h2 style='color:orange;'>需要至少 3 個變動參數才能畫 3D 圖</h2>"

    elif chart_type == "平行座標圖 (多參數)":
        dims = varying_params + ["metric"]
        fig = px.parallel_coordinates(df, dimensions=dims, color="metric", color_continuous_scale=px.colors.diverging.RdYlGn, labels={"metric": metric_zh})
        return _wrap_html(fig, "多參數平行座標分析")

    elif chart_type == "分面熱力圖 (3參數)":
        if len(varying_params) >= 3:
            x, y, facet = varying_params[0], varying_params[1], varying_params[2]
            pivot_df = df.groupby([facet, x, y])["metric"].mean().reset_index()
            fig = px.density_heatmap(pivot_df, x=x, y=y, z="metric", facet_col=facet, histfunc="avg", text_auto=".2f", color_continuous_scale="RdYlGn", labels={"metric": metric_zh})
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            return _wrap_html(fig, f"分面熱力圖 (依 {facet} 展開)")
        return "<h2 style='color:orange;'>需要至少 3 個變動參數才能畫分面圖</h2>"

    elif chart_type == "氣泡圖 (3參數)":
        if len(varying_params) >= 3:
            x, y, size = varying_params[0], varying_params[1], varying_params[2]
            fig = px.scatter(df, x=x, y=y, size=size, color="metric", color_continuous_scale="RdYlGn", hover_data=varying_params, labels={"metric": metric_zh})
            return _wrap_html(fig, "多維氣泡圖")
        return "<h2 style='color:orange;'>需要至少 3 個變動參數才能畫氣泡圖</h2>"

    elif chart_type == "多變數迴歸分析":
        # 💡 這裡實作了你 V2 的線性迴歸邏輯
        X = df[varying_params].copy()
        y = df["metric"]
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors='coerce')
        valid_idx = X.dropna().index
        X, y = X.loc[valid_idx], y.loc[valid_idx]
        
        if len(X) < len(varying_params) + 1:
            return "<h2 style='color:orange;'>資料量太少，無法進行迴歸分析</h2>"
            
        model = LinearRegression().fit(X, y)
        r2 = model.score(X, y)
        
        coef_df = pd.DataFrame({
            "參數": varying_params,
            "迴歸係數": model.coef_,
            "絕對值": np.abs(model.coef_)
        }).sort_values(by="絕對值", ascending=False)
        
        # 只取影響力前 10 名畫圖
        coef_df = coef_df.head(10)
        
        fig = px.bar(
            coef_df, x='迴歸係數', y='參數', orientation='h',
            title=f"參數影響力 (R² = {r2:.2%})",
            template="plotly_dark", color='迴歸係數', color_continuous_scale="RdYlGn"
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        return _wrap_html(fig, f"多變數迴歸 - 模型解釋力 R² = {r2:.2%}")

    return "<h2 style='color:white;'>未知的圖表類型</h2>"