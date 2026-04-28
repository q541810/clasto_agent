# ==========================================
# Napcat 适配器入口文件
# 功能：被 启动适配器.py 扫描并启动
# ==========================================
import subprocess
import sys
import os

def 启动napcat适配器():
    """
    启动 Napcat 适配器进程
    """
    from 模块.log模块 import logger
    
    当前目录 = os.path.dirname(os.path.abspath(__file__))
    适配器路径 = os.path.join(当前目录, "napcat_adapter.py")
    
    logger.info("正在启动 Napcat 适配器...")
    
    if sys.platform == "win32":
        subprocess.Popen(
            ["python", 适配器路径],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        subprocess.Popen(["python", 适配器路径])
    
    logger.info("Napcat 适配器已在独立进程中启动")


if __name__ == "__main__":
    启动napcat适配器()
