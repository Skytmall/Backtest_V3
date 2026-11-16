# src/core/export/formatters.py
from abc import ABC, abstractmethod
from typing import List
from .config import ExportConfig
from .extractor import TradeWindow


class BaseFormatter(ABC):
    """未來的 JSON / YAML 格式只需繼承此類。"""
    extension: str = ".txt"

    @abstractmethod
    def format(self, result: dict, config: ExportConfig, windows: List[TradeWindow]) -> str:
        pass


class MarkdownFormatter(BaseFormatter):
    extension = ".md"

    def format(self, result: dict, config: ExportConfig, windows: List[TradeWindow]) -> str:
        parts = [self._header(result)]
        if config.include_summary:
            parts.append(self._summary(result))
        
        for w in windows:
            parts.append(self._window(w))
            
        return "\n\n---\n\n".join(parts)

    def _header(self, result):
        return f"# 交易窗口診斷包 — {result.get('ticker', '?')} / {result.get('strat_id', '?')}"

    def _summary(self, result):
        m = result.get("is", {}).get("metrics", {})
        params = ", ".join(f"{k}={v}" for k, v in result.get("params", {}).items())
        return f"""## 全局績效摘要
- **參數**：{params}
- **總報酬**：{m.get('Total_Return', 0):.2%} | **年化**：{m.get('CAGR', 0):.2%}
- **夏普**：{m.get('Sharpe_Ratio', 0):.2f} | **最大回撤**：{m.get('Max_Drawdown', 0):.2%}
- **勝率**：{m.get('Win_Rate', 0):.1%} | **交易次數**：{m.get('Total_Trades', 0)}"""

    def _window(self, w: TradeWindow):
        cols = ["mark", "Open", "High", "Low", "Close"]
        if "Volume" in w.window_df.columns:
            cols.append("Volume")
        cols += [c for c in w.indicator_cols if c in w.window_df.columns]

        df = w.window_df[cols].round(2)
        df.index.name = "Date"
        csv_text = df.to_csv().rstrip()
        hold = (w.exit_date - w.entry_date).days

        return f"""### #{w.rank} {w.tag} — {w.ret:+.2%}

| 進場 | 出場 | 持有 | 股數 | 出場原因 |
|---|---|---|---|---|
| {w.entry_date.strftime('%Y-%m-%d')} @ {w.entry_price:.2f} | {w.exit_date.strftime('%Y-%m-%d')} @ {w.exit_price:.2f} | {hold} 天 | {w.shares:,} | {w.exit_reason} |

```csv
{csv_text}
```"""


class HTMLFormatter(BaseFormatter):
    extension = ".html"

    def format(self, result: dict, config: ExportConfig, windows: List[TradeWindow]) -> str:
        parts = [self._header(result)]
        if config.include_summary:
            parts.append(self._summary(result))
        for w in windows:
            parts.append(self._window(w))
            
        html_body = "\n".join(parts)
        
        # 加上深色模式的 CSS
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{result.get('ticker')} 診斷包</title>
<style>
  body {{ font-family: "Microsoft JhengHei", sans-serif; background-color: #1e1e1e; color: #e0e0e0; padding: 20px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 14px; }}
  th, td {{ border: 1px solid #444; padding: 8px; text-align: center; }}
  th {{ background-color: #2d2d30; color: #fff; }}
  h1, h2, h3 {{ color: #fafafa; }}
  .data {{ background-color: #252526; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    def _header(self, result):
        return f"<h1>交易窗口診斷包 — {result.get('ticker', '?')} / {result.get('strat_id', '?')}</h1>"

    def _summary(self, result):
        m = result.get("is", {}).get("metrics", {})
        params = ", ".join(f"{k}={v}" for k, v in result.get("params", {}).items())
        return f"""<h2>全局績效摘要</h2>
<ul>
  <li><strong>參數</strong>：{params}</li>
  <li><strong>總報酬</strong>：{m.get('Total_Return', 0):.2%} | <strong>年化</strong>：{m.get('CAGR', 0):.2%}</li>
  <li><strong>夏普</strong>：{m.get('Sharpe_Ratio', 0):.2f} | <strong>最大回撤</strong>：{m.get('Max_Drawdown', 0):.2%}</li>
  <li><strong>勝率</strong>：{m.get('Win_Rate', 0):.1%} | <strong>交易次數</strong>：{m.get('Total_Trades', 0)}</li>
</ul>"""

    def _window(self, w: TradeWindow):
        cols = ["mark", "Open", "High", "Low", "Close"]
        if "Volume" in w.window_df.columns:
            cols.append("Volume")
        cols += [c for c in w.indicator_cols if c in w.window_df.columns]

        df = w.window_df[cols].round(2)
        df.index.name = "Date"
        hold = (w.exit_date - w.entry_date).days

        table_html = df.to_html(classes='data', header=True)
        
        return f"""<h3>#{w.rank} {w.tag} — {w.ret:+.2%}</h3>
<table>
<tr><th>進場</th><th>出場</th><th>持有</th><th>股數</th><th>出場原因</th></tr>
<tr>
  <td>{w.entry_date.strftime('%Y-%m-%d')} @ {w.entry_price:.2f}</td>
  <td>{w.exit_date.strftime('%Y-%m-%d')} @ {w.exit_price:.2f}</td>
  <td>{hold} 天</td>
  <td>{w.shares:,}</td>
  <td>{w.exit_reason}</td>
</tr>
</table>
{table_html}"""