import os
import subprocess
import sys
from 模块.log模块 import logger

def 启动适配器():
    """
    读取 模块\适配器 目录下的所有适配器文件并启动它们
    """
    # 获取当前文件所在的目录路径
    当前目录 = os.path.dirname(os.path.abspath(__file__))
    # 拼接适配器目录的路径
    适配器目录 = os.path.join(当前目录, "适配器")
    
    logger.info(f"正在扫描适配器目录: {适配器目录}")
    
    if not os.path.exists(适配器目录):
        logger.error(f"错误: 找不到适配器目录 {适配器目录}")
        return

    try:
        所有文件 = os.listdir(适配器目录)
        适配器文件 = [文件 for 文件 in 所有文件 if 文件.endswith(".py") and 文件 != "__init__.py"]
        
        if not 适配器文件:
            logger.warning("未发现可用的适配器文件。")
            return

        logger.info(f"发现 {len(适配器文件)} 个适配器，准备启动...")
        

        for 文件名 in 适配器文件:
            文件路径 = os.path.join(适配器目录, 文件名)
            适配器名称 = 文件名[:-3]
            
            logger.info(f"正在启动适配器进程: {适配器名称}")
            
            # 在 Windows 上开启新窗口运行适配器，以便进行 input() 交互
            if sys.platform == "win32":
                subprocess.Popen(
                    ["python", 文件路径],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # 非 Windows 系统则在后台运行 (可能无法直接交互)
                subprocess.Popen(["python", 文件路径])
                
            logger.info(f"适配器 {适配器名称} 已在独立进程中启动。")
                
    except Exception as 错误:
        logger.error(f"启动适配器时发生错误: {错误}")

if __name__ == "__main__":
    # 本地测试
    启动适配器()
