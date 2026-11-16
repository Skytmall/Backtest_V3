Set WshShell = CreateObject("WScript.Shell")
' 將 "python" 替換成你的 python 路徑，例如 python.exe 或 pythonw.exe
WshShell.CurrentDirectory = "C:\Users\Skytmall\Desktop\Backtest_v3"
WshShell.Run "cmd /c python src\main.py", 0, False