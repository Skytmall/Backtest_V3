# core/ultimate_tracer.py
import sys
import os
import datetime
import threading

ULTIMATE_TRACE_MODE = False  # 💡 預設開啟
LOG_DIR = "trace_logs"      # 💡 日誌資料夾

class UltimateTracer:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

    def start_thread_trace(self):
        """在背景執行緒中啟動追蹤"""
        if not ULTIMATE_TRACE_MODE:
            return
        
        # 取得當前執行緒名稱（例如 ThreadPoolExecutor-0_1）
        thread_name = threading.current_thread().name.replace("_", "-")
        log_path = os.path.join(LOG_DIR, f"trace_{thread_name}.log")
        
        # 把 log 路徑存進執行緒的區域變數，方便寫入
        threading.current_thread().trace_log_path = log_path

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== Thread Trace Started at {datetime.datetime.now()} ===\n")
            
        sys.settrace(self._trace_calls)

    def stop_thread_trace(self):
        """停止追蹤"""
        if ULTIMATE_TRACE_MODE:
            sys.settrace(None)

    def _trace_calls(self, frame, event, arg):
        filename = frame.f_code.co_filename
        
        # 只追蹤我們專案內的檔案
        if not filename.startswith(self.project_root):
            return None
            
        short_filename = os.path.basename(filename)
        func_name = frame.f_code.co_name
        lineno = frame.f_lineno
        
        if event == 'call':
            self._write_log(f"\n[ CALL ] {short_filename}:{lineno} -> {func_name}()")
            return self._trace_lines
            
        elif event == 'exception':
            exc_type, exc_value, exc_traceback = arg
            self._write_log(f"❌ [EXCEPTION] {short_filename}:{lineno} in {func_name}(): {exc_type.__name__}: {exc_value}")
            # 抓取發生異常當下的區域變數
            local_vars = {k: repr(v)[:100] for k, v in frame.f_locals.items() if not k.startswith('__')}
            self._write_log(f"   👉 Locals: {local_vars}")
            
        return self._trace_calls

    def _trace_lines(self, frame, event, arg):
        if event == 'line':
            filename = frame.f_code.co_filename
            if not filename.startswith(self.project_root):
                return self._trace_lines
                
            short_filename = os.path.basename(filename)
            func_name = frame.f_code.co_name
            lineno = frame.f_lineno
            
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    code_line = lines[lineno - 1].strip()
            except Exception:
                code_line = "<無法讀取>"
                
            self._write_log(f"   Line {lineno} [{func_name}]: {code_line}")
            
        elif event == 'return':
            self._write_log(f"[ RETURN] {os.path.basename(frame.f_code.co_filename)} -> {frame.f_code.co_name}")
            
        return self._trace_lines

    def _write_log(self, msg):
        log_path = getattr(threading.current_thread(), "trace_log_path", None)
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")

tracer = UltimateTracer()