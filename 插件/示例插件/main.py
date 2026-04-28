# ==========================================
# 示例插件 (示例插件/main.py)
# 功能：展示插件系统的基本用法
# ==========================================

from 模块.log模块 import logger


async def 入口(上下文):
    """
    插件入口函数，启动时调用一次
    上下文是 插件上下文 对象，提供以下API：
    - 上下文.注册工具(名称, 工具函数, 别名, 参数说明, 说明, 是否回复工具)
    - 上下文.注册钩子(hook名, 回调)
    - 上下文.调用适配器API(action, params)
    - 上下文.获取聊天流(chat_id)
    - 上下文.发送消息(chat_id, chat_type, message)
    - 上下文.获取配置(键=None)
    """

    greeting = 上下文.获取配置("greeting", "你好")
    logger.info(f"[示例插件] 初始化完成，配置 greeting={greeting}")

    上下文.注册工具(
        名称="示例工具",
        工具函数=示例工具函数,
        别名=["示例工具别名"],
        参数说明={"关键词": "要查询的关键词"},
        说明="一个示例工具，返回固定文本",
    )

    上下文.注册钩子("on_message_receive", 消息接收钩子)
    上下文.注册钩子("on_post_reply", 回复后钩子)


async def 示例工具函数(**参数):
    """
    示例工具函数
    """
    关键词 = 参数.get("关键词", "")
    聊天流 = 参数.get("_聊天流")
    return {
        "status": "success",
        "message": f"示例工具执行成功，关键词: {关键词}",
        "data": {"关键词": 关键词}
    }


async def 消息接收钩子(消息数据: dict) -> dict:
    """
    on_message_receive 钩子回调
    在消息进入主程序时触发
    返回修改后的消息数据，或返回 None 拦截消息
    """
    消息内容 = 消息数据.get("message", "")
    if 消息内容 == "__test_block__":
        logger.info("[示例插件] 拦截了测试消息")
        return None
    return 消息数据


async def 回复后钩子(回复内容: str) -> str:
    """
    on_post_reply 钩子回调
    在回复模型输出后触发，可修改回复内容
    返回修改后的回复内容
    """
    return 回复内容