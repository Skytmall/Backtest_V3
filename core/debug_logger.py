# src/core/debug_logger.py
import inspect
import functools
import threading
from datetime import datetime
from typing import Callable, Any

from core.paths import LOGS_DIR

DEBUG_MODE = False
DEBUG_LOG_FILE = LOGS_DIR / "debug.log"


def _write_log(msg: str) -> None:
    """單行寫檔；多執行緒安全（單行 < 4KB，OS 保證原子性）。"""
    with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def trace_call(func: Callable) -> Callable:
    """裝飾器：若開啟 DEBUG_MODE，則把呼叫來源寫入 debug.log。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        if DEBUG_MODE:
            stack = inspect.stack()
            caller_frame = stack[1]
            caller_name = caller_frame.function
            caller_file = caller_frame.filename.replace("\\", "/").split("/")[-1]
            callee_name = func.__name__
            time_str = datetime.now().strftime("%H:%M:%S")
            _write_log(f"[{time_str}] 🔍 [Call] {caller_file}::{caller_name} ➔ {callee_name}")
        return func(*args, **kwargs)
    return wrapper


def log_decision(component: str, message: str) -> None:
    """記錄交易決策，方便追「為什麼沒進場/沒出場」。"""
    if DEBUG_MODE:
        time_str = datetime.now().strftime("%H:%M:%S")
        thread_name = threading.current_thread().name.split("_")[-1]
        _write_log(f"[{time_str}] 🧠 [決策-{thread_name}] [{component}] {message}")