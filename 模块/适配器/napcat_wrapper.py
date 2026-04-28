# ==========================================
# Napcat 适配器启动文件
# 功能：被 启动适配器.py 扫描并启动 Napcat 适配器
# ==========================================
import subprocess
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def 启动napcat适配器():
    """
    启动 Napcat 适配器进程
    """
    from 模块.log模块 import logger
    
    当前目录 = os.path.dirname(os.path.abspath(__file__))
    适配器路径 = os.path.join(当前目录, "napcat", "napcat_adapter.py")
    
    if not os.path.exists(适配器路径):
        logger.error(f"找不到 Napcat 适配器文件: {适配器路径}")
        return
    
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
