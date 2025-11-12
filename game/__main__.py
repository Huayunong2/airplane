import sys
import os

# 兼容：包内运行与脚本/打包环境（如 PyInstaller）
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from .main_menu import run
except Exception:
    from game.main_menu import run

if __name__ == "__main__":
    run()

