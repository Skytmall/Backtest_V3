# src/core/paths.py
from pathlib import Path

SRC_DIR      = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_DIR.parent

# 運行期資料
RUNTIME_DATA_DIR = PROJECT_ROOT / "runtime_data"
DATA_CACHE_DIR   = RUNTIME_DATA_DIR / "data_cache"
SAVES_DIR        = RUNTIME_DATA_DIR / "saves"

# ==== 新增：三大板塊的專屬存檔資料夾 ====
SAVES_ENV_DIR        = SAVES_DIR / "env"
SAVES_STOCKS_DIR     = SAVES_DIR / "stocks"
SAVES_STRATEGIES_DIR = SAVES_DIR / "strategies"

# 開發調試
DEV_TOOLS_DIR = PROJECT_ROOT / "dev_tools"
LOGS_DIR      = DEV_TOOLS_DIR / "logs"
CACHES_DIR    = DEV_TOOLS_DIR / "caches"
SCRIPTS_DIR   = DEV_TOOLS_DIR / "scripts"

# AI 診斷包緩存
AI_CONTEXT_CACHE_DIR = CACHES_DIR / "ai_context"

# 設定檔
SETTINGS_FILE = SRC_DIR / "settings.json"

# 環境匯入範例目錄
ENV_TEMPLATES_DIR = RUNTIME_DATA_DIR / "env_templates"
# 股票自訂名單
WATCHLIST_FILE = RUNTIME_DATA_DIR / "watchlist.json"

for d in (DATA_CACHE_DIR, SAVES_DIR, LOGS_DIR, CACHES_DIR, SCRIPTS_DIR,
          AI_CONTEXT_CACHE_DIR, ENV_TEMPLATES_DIR, 
          SAVES_ENV_DIR, SAVES_STOCKS_DIR, SAVES_STRATEGIES_DIR):  # <-- 加在這裡
    d.mkdir(parents=True, exist_ok=True)