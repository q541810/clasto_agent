import asyncio
import websockets
import sys
import os
import json

# 导入日志模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from 模块.log模块 import logger

# ==========================================
# OneBot v11 适配器
# 功能：接收 OneBot v11 协议消息，转换为统一格式发送给主程序
# ==========================================
#
# 适配器发送的消息格式:
# {
#     "adapter": "onebot_v11",
#     "chat_id": "group_123456" 或 "private_789012",
#     "chat_type": "group" 或 "private",
#     "sender_id": 发送者QQ号,
#     "sender_name": "发送者昵称",
#     "message": "消息内容",
#     "raw_data": {...}  # 原始 OneBot v11 数据
# }
#
# chat_id 规则:
#   - 群聊: "group_{group_id}"
#   - 私聊: "private_{user_id}"
# ==========================================

async def 监听连接断开(连接对象):
    """
    后台任务：专门监听连接是否断开
    """
    await 连接对象.wait_closed()
    logger.warning("检测到主程序已关闭，适配器正在强制退出...")
    os._exit(0)

def 解析消息类型(原始数据: dict) -> tuple:
    """
    解析 OneBot v11 消息，提取聊天ID和聊天类型
    返回: (chat_id, chat_type)
    """
    message_type = 原始数据.get("message_type", "")
    
    if message_type == "group":
        group_id = 原始数据.get("group_id", 0)
        chat_id = f"group_{group_id}"
        chat_type = "group"
    elif message_type == "private":
        user_id = 原始数据.get("user_id", 0)
        chat_id = f"private_{user_id}"
        chat_type = "private"
    else:
        # 未知类型，使用 user_id 作为 fallback
        user_id = 原始数据.get("user_id", 0)
        chat_id = f"unknown_{user_id}"
        chat_type = "private"
    
    return chat_id, chat_type

def 提取消息内容(原始数据: dict) -> str:
    """
    从 OneBot v11 消息中提取纯文本内容
    支持 string 格式和 message segment 数组格式
    """
    message = 原始数据.get("message", "")
    
    if isinstance(message, str):
        return message
    elif isinstance(message, list):
        # message segment 数组格式，提取所有 text 类型
        文本列表 = []
        for 段 in message:
            if isinstance(段, dict) and 段.get("type") == "text":
                文本列表.append(段.get("data", {}).get("text", ""))
        return "".join(文本列表)
    
    return str(message)

def 构建统一消息(原始数据: dict) -> dict:
    """
    将 OneBot v11 原始消息转换为统一格式
    """
    chat_id, chat_type = 解析消息类型(原始数据)
    消息内容 = 提取消息内容(原始数据)
    
    统一消息 = {
        "adapter": "onebot_v11",
        "chat_id": chat_id,
        "chat_type": chat_type,
        "sender_id": 原始数据.get("user_id", 0),
        "sender_name": 原始数据.get("sender", {}).get("nickname", "") or 原始数据.get("user_id", ""),
        "message": 消息内容,
        "raw_data": 原始数据
    }
    
    return 统一消息

async def 启动客户端():
    """
    WebSocket 客户端，负责连接主程序并转发消息
    """
    服务器地址 = "ws://localhost:8081"
    
    logger.info(f"正在尝试连接到主程序: {服务器地址}")
    
    try:
        async with websockets.connect(服务器地址) as 协议连接:
            logger.info("连接成功！OneBot v11 适配器已就绪。")
            
            # 启动后台监听任务
            asyncio.create_task(监听连接断开(协议连接))
            
            # TODO: 这里后续接入真实的 OneBot v11 服务端
            # 目前使用 input() 模拟接收消息
            
            while True:
                输入内容 = await asyncio.get_event_loop().run_in_executor(
                    None, input, "请输入要发送给主程序的消息: "
                )
                
                if 输入内容.lower() in ['exit', 'quit', '退出']:
                    logger.info("正在退出适配器...")
                    break
                
                if 输入内容.strip():
                    # 模拟 OneBot v11 消息格式
                    模拟原始数据 = {
                        "time": int(asyncio.get_event_loop().time()),
                        "self_id": 123456,
                        "post_type": "message",
                        "message_type": "group",
                        "sub_type": "normal",
                        "message_id": 1,
                        "group_id": 111222,
                        "user_id": 789012,
                        "sender": {"nickname": "测试用户"},
                        "message": 输入内容
                    }
                    
                    统一消息 = 构建统一消息(模拟原始数据)
                    await 协议连接.send(json.dumps(统一消息, ensure_ascii=False))
                    logger.info(f"已发送消息: {统一消息['message']}")
                    
    except ConnectionRefusedError:
        logger.error("连接失败：主程序 WebSocket 服务端未启动或拒绝连接。")
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as 错误:
        logger.error(f"适配器运行过程中发生错误: {错误}")
    finally:
        logger.info("适配器进程已结束。")
        os._exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(启动客户端())
    except KeyboardInterrupt:
        pass
