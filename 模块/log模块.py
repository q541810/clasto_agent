from loguru import logger
import sys

# 1. 移除默认配置 (默认输出到 stderr)
logger.remove()

# 2. 自定义控制台输出格式
日志格式 = (
    "<green>{time: HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:"
    "<level>{message}</level>"
)

# 添加控制台输出，默认INFO级别
控制台处理器 = logger.add(sys.stdout, format=日志格式, level="INFO", colorize=True)

def 设置调试模式():
    """
    切换到调试模式，显示DEBUG级别日志
    """
    global 控制台处理器
    logger.remove(控制台处理器)
    控制台处理器 = logger.add(sys.stdout, format=日志格式, level="DEBUG", colorize=True)

# 3. 仅保留控制台输出，不再保存到文件
# 如果将来需要保存文件，可以使用 logger.add("文件名.log", ...)

def 获取日志器():
    """
    返回配置好的日志对象
    """
    return logger

if __name__ == "__main__":
    # 测试代码
    logger.debug("这是一条调试信息 (通常只在文件里看到)")
    logger.info("这是一条普通信息 (控制台和文件都能看到)")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("捕获到一个异常！")
