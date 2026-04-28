import asyncio
import websockets
import sys
import os
import json
import http
import toml
import time
import uuid

# 导入日志模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from 模块.log模块 import logger

# ==========================================
# Napcat 适配器
# 功能：连接 Napcat (OneBot v11)，转换为统一格式发送给 Clasto Agent 主程序
#       同时接收主程序的回复消息，通过 Napcat API 发送回 QQ
#
# 支持两种连接模式:
#   forward (正向WS): 适配器作为WS客户端，主动连接 Napcat 的 WS 服务端
#   reverse (反向WS): 适配器作为WS服务端，等待 Napcat 反向连接
# ==========================================

# 配置文件路径
配置文件路径 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")

def 加载配置():
    """
    从 config.toml 加载配置
    """
    默认配置 = {
        "connection_mode": "forward",
        "napcat_server": {
            "host": "192.168.1.49",
            "port": 3001,
            "token": "",
            "heartbeat_interval": 30
        },
        "clasto_agent": {
            "host": "localhost",
            "port": 8081
        }
    }
    
    if not os.path.exists(配置文件路径):
        logger.warning(f"配置文件不存在: {配置文件路径}，使用默认配置")
        return 默认配置
    
    try:
        with open(配置文件路径, "r", encoding="utf-8") as f:
            配置 = toml.load(f)
        
        # 合并默认配置，确保字段完整
        for 键 in 默认配置:
            if 键 not in 配置:
                配置[键] = 默认配置[键]
            else:
                if isinstance(默认配置[键], dict):
                    for 子键 in 默认配置[键]:
                        if 子键 not in 配置[键]:
                            配置[键][子键] = 默认配置[键][子键]
        
        logger.info(f"配置文件加载成功: {配置文件路径}")
        return 配置
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}，使用默认配置")
        return 默认配置

# 加载配置
配置 = 加载配置()

# 全局配置
CONNECTION_MODE = 配置.get("connection_mode", "forward")  # "forward" 或 "reverse"
NAPCAT_HOST = 配置["napcat_server"]["host"]
NAPCAT_PORT = 配置["napcat_server"]["port"]
NAPCAT_TOKEN = 配置["napcat_server"]["token"]
HEARTBEAT_INTERVAL = 配置["napcat_server"]["heartbeat_interval"]

# 主程序地址
MAIN_HOST = 配置["clasto_agent"]["host"]
MAIN_PORT = 配置["clasto_agent"]["port"]

# 会话筛选配置（群聊和私聊分别配置）
_sf = 配置.get("session_filter", {})
_sf_groups = _sf.get("groups", {})
_sf_users = _sf.get("users", {})

SESSION_FILTER_GROUP_MODE = _sf_groups.get("mode", "none")
SESSION_FILTER_GROUP_LIST = [str(g) for g in _sf_groups.get("list", [])]

SESSION_FILTER_USER_MODE = _sf_users.get("mode", "none")
SESSION_FILTER_USER_LIST = [str(u) for u in _sf_users.get("list", [])]

# 全局变量
napcat_connection = None  # Napcat 的 WS 连接（正向=客户端连接，反向=服务端连接）
clasto_connection = None  # 连接主程序的 WS 客户端
response_pool = {}  # 用于存储 API 调用的响应 {echo: response}
last_heartbeat_time = 0  # 上次心跳时间
连续连接主程序失败次数 = 0  # 连续连接主程序失败的次数


# ==========================================
# 消息处理工具函数
# ==========================================

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
        user_id = 原始数据.get("user_id", 0)
        chat_id = f"unknown_{user_id}"
        chat_type = "private"
    
    return chat_id, chat_type


def 会话筛选(原始数据: dict) -> bool:
    """
    检查消息是否通过会话筛选
    返回 True = 允许转发, False = 拦截
    """
    message_type = 原始数据.get("message_type", "")
    
    if message_type == "group":
        session_id = str(原始数据.get("group_id", 0))
        session_type = "群聊"
        筛选模式 = SESSION_FILTER_GROUP_MODE
        筛选列表 = SESSION_FILTER_GROUP_LIST
    elif message_type == "private":
        session_id = str(原始数据.get("user_id", 0))
        session_type = "私聊"
        筛选模式 = SESSION_FILTER_USER_MODE
        筛选列表 = SESSION_FILTER_USER_LIST
    else:
        return True  # 未知类型默认放行
    
    if 筛选模式 == "none":
        return True
    elif 筛选模式 == "whitelist":
        if session_id in 筛选列表:
            return True
        logger.debug(f"会话拦截(白名单): {session_type} {session_id} 不在白名单中")
        return False
    elif 筛选模式 == "blacklist":
        if session_id in 筛选列表:
            logger.debug(f"会话拦截(黑名单): {session_type} {session_id} 在黑名单中")
            return False
        return True
    
    return True


def 提取消息内容(原始数据: dict) -> str:
    """
    从 OneBot v11 消息中提取纯文本内容
    支持 string 格式和 message segment 数组格式
    """
    message = 原始数据.get("message", "")
    
    if isinstance(message, str):
        return message
    elif isinstance(message, list):
        文本列表 = []
        for 段 in message:
            if isinstance(段, dict):
                if 段.get("type") == "text":
                    文本列表.append(段.get("data", {}).get("text", ""))
                elif 段.get("type") == "image":
                    文本列表.append("[图片]")
                elif 段.get("type") == "face":
                    文本列表.append("[表情]")
                elif 段.get("type") == "at":
                    qq = 段.get("data", {}).get("qq", "")
                    if qq == "all":
                        文本列表.append("@全体成员")
                    else:
                        文本列表.append(f"@{qq}")
                elif 段.get("type") == "reply":
                    文本列表.append("[回复]")
                elif 段.get("type") == "forward":
                    文本列表.append("[转发消息]")
                elif 段.get("type") == "file":
                    文本列表.append(f"[文件: {段.get('data', {}).get('file', '未知')}]")
                elif 段.get("type") == "record":
                    文本列表.append("[语音]")
                elif 段.get("type") == "video":
                    文本列表.append("[视频]")
                elif 段.get("type") == "json":
                    文本列表.append("[卡片消息]")
                elif 段.get("type") == "xml":
                    文本列表.append("[XML卡片]")
                elif 段.get("type") == "poke":
                    文本列表.append("[戳一戳]")
        return "".join(文本列表)
    
    return str(message)


def 构建统一消息(原始数据: dict) -> dict:
    """
    将 OneBot v11 原始消息转换为统一格式
    """
    chat_id, chat_type = 解析消息类型(原始数据)
    消息内容 = 提取消息内容(原始数据)
    
    sender_info = 原始数据.get("sender", {})
    
    统一消息 = {
        "adapter": "napcat",
        "chat_id": chat_id,
        "chat_type": chat_type,
        "sender_id": 原始数据.get("user_id", 0),
        "sender_name": sender_info.get("nickname", "") or str(原始数据.get("user_id", "")),
        "message": 消息内容,
        "message_segments": 原始数据.get("message", []),
        "message_id": 原始数据.get("message_id", 0),
        "self_id": 原始数据.get("self_id", 0),
        "raw_data": 原始数据
    }
    
    return 统一消息


def 解析chat_id(chat_id: str, chat_type: str) -> int:
    """
    解析 chat_id 为纯数字ID
    兼容带前缀("group_123"/"private_456")和不带前缀("123")两种格式
    """
    if chat_type == "group":
        return int(chat_id.replace("group_", ""))
    elif chat_type == "private":
        return int(chat_id.replace("private_", ""))
    else:
        return int(chat_id)


# ==========================================
# 核心消息处理逻辑
# ==========================================

async def 处理napcat消息(原始消息: dict):
    """
    处理从 Napcat 收到的消息
    """
    global clasto_connection, response_pool, last_heartbeat_time
    
    post_type = 原始消息.get("post_type")
    
    # 处理 API 响应
    echo = 原始消息.get("echo")
    if echo:
        response_pool[echo] = 原始消息
        logger.debug(f"收到 API 响应: {echo}")
        return
    
    # 处理心跳
    if post_type == "meta_event":
        meta_event_type = 原始消息.get("meta_event_type", "")
        if meta_event_type == "heartbeat":
            last_heartbeat_time = time.time()
            status = 原始消息.get("status", {})
            logger.debug(f"收到 Napcat 心跳: 在线={status.get('online', '?')}, 好={status.get('good', '?')}")
        return
    
    # 处理消息
    if post_type == "message":
        统一消息 = 构建统一消息(原始消息)
        logger.info(f"收到消息: [{统一消息['chat_type']}] {统一消息['sender_name']}: {统一消息['message'][:50]}")
        
        # 发送到主程序
        if clasto_connection:
            try:
                await clasto_connection.send(json.dumps(统一消息, ensure_ascii=False))
                logger.debug(f"已转发消息到主程序: {统一消息['chat_id']}")
            except Exception as e:
                logger.error(f"发送消息到主程序失败: {e}")
        else:
            logger.error("未连接到主程序，消息被丢弃")
        return
    
    # 处理通知
    if post_type == "notice":
        notice_type = 原始消息.get("notice_type", "")
        logger.debug(f"收到通知: {notice_type}")
        return
    
    logger.debug(f"未知的 post_type: {post_type}")


async def 处理主程序消息(消息数据: dict):
    """
    处理从主程序收到的消息
    """
    global response_pool
    
    echo = 消息数据.get("echo")
    
    # 如果是 API 响应（有 echo 字段）
    if echo and echo in response_pool:
        response_pool[echo] = 消息数据
        logger.debug(f"收到 API 响应: {echo}")
        return
    
    # 否则是普通回复消息
    action = 消息数据.get("action", "")
    
    if action == "send_message":
        await 发送消息到napcat(消息数据)
    elif action == "call_api":
        await 调用NapcatAPI(消息数据)
    elif action == "shutdown":
        logger.info("收到主程序关闭信号，适配器正在退出...")
        os._exit(0)
    else:
        logger.warning(f"未知的主程序消息 action: {action}")


async def 发送消息到napcat(消息数据: dict):
    """
    将消息发送到 Napcat
    """
    global napcat_connection
    
    if not napcat_connection:
        logger.error("Napcat 未连接，无法发送消息")
        return
    
    chat_type = 消息数据.get("chat_type", "")
    chat_id = 消息数据.get("chat_id", "")
    message = 消息数据.get("message", "")
    reply_to = 消息数据.get("reply_to")
    
    # 解析 chat_id 为纯数字
    try:
        目标ID = 解析chat_id(chat_id, chat_type)
    except (ValueError, TypeError) as e:
        logger.error(f"chat_id 格式无效: {chat_id}, 错误: {e}")
        return
    
    request_uuid = str(uuid.uuid4())
    
    # 构建消息体
    if reply_to:
        message_body = [
            {"type": "reply", "data": {"id": str(reply_to)}},
            {"type": "text", "data": {"text": message}}
        ]
    else:
        message_body = message
    
    # 构建 OneBot v11 发送请求
    params = {"message": message_body}
    if chat_type == "group":
        params["group_id"] = 目标ID
    elif chat_type == "private":
        params["user_id"] = 目标ID
    else:
        logger.error(f"未知的 chat_type: {chat_type}")
        return
    
    payload = json.dumps({
        "action": "send_msg",
        "params": params,
        "echo": request_uuid
    })
    
    try:
        await napcat_connection.send(payload)
        logger.info(f"已向 Napcat 发送消息: {chat_id} -> {message[:50]}")
    except Exception as e:
        logger.error(f"向 Napcat 发送消息失败: {e}")


async def 调用NapcatAPI(消息数据: dict):
    """
    处理主程序发来的 call_api 请求，转发到 Napcat 并将响应返回给主程序
    """
    global napcat_connection, response_pool
    
    if not napcat_connection:
        响应 = {"status": "error", "message": "Napcat 未连接", "echo": 消息数据.get("echo")}
        await 发送响应回主程序(响应)
        return
    
    api_action = 消息数据.get("api_action", "")
    api_params = 消息数据.get("api_params", {})
    echo = 消息数据.get("echo", "")
    
    request_uuid = str(uuid.uuid4())
    response_pool[request_uuid] = None
    
    payload = json.dumps({
        "action": api_action,
        "params": api_params,
        "echo": request_uuid
    })
    
    try:
        await napcat_connection.send(payload)
        
        for _ in range(150):
            if response_pool.get(request_uuid) is not None:
                结果 = response_pool.pop(request_uuid)
                结果["echo"] = echo
                await 发送响应回主程序(结果)
                return
            await asyncio.sleep(0.1)
        
        response_pool.pop(request_uuid, None)
        await 发送响应回主程序({"status": "error", "message": "超时", "echo": echo})
    except Exception as e:
        response_pool.pop(request_uuid, None)
        await 发送响应回主程序({"status": "error", "message": str(e), "echo": echo})


async def 发送响应回主程序(响应数据: dict):
    """
    将API响应发送回主程序
    """
    global clasto_connection
    if clasto_connection:
        try:
            await clasto_connection.send(json.dumps(响应数据, ensure_ascii=False))
        except Exception as e:
            logger.error(f"发送API响应回主程序失败: {e}")
    else:
        logger.error("未连接到主程序，无法发送API响应")


async def 调用napcatAPI(action: str, params: dict, timeout: int = 10) -> dict:
    """
    调用 Napcat API 并等待响应
    """
    global napcat_connection, response_pool
    
    if not napcat_connection:
        logger.error("Napcat 未连接，无法调用 API")
        return {"status": "error", "message": "not connected"}
    
    request_uuid = str(uuid.uuid4())
    
    payload = json.dumps({
        "action": action,
        "params": params,
        "echo": request_uuid
    })
    
    response_pool[request_uuid] = None
    
    try:
        await napcat_connection.send(payload)
        
        # 等待响应
        for _ in range(timeout * 10):
            if response_pool.get(request_uuid) is not None:
                return response_pool.pop(request_uuid)
            await asyncio.sleep(0.1)
        
        response_pool.pop(request_uuid, None)
        logger.error(f"API 调用超时: {action}")
        return {"status": "error", "message": "timeout"}
    except Exception as e:
        response_pool.pop(request_uuid, None)
        logger.error(f"API 调用失败: {action}, 错误: {e}")
        return {"status": "error", "message": str(e)}


# ==========================================
# 连接管理
# ==========================================

async def 连接到主程序():
    """
    作为客户端连接到 Clasto Agent 主程序
    连续失败2次则自动关闭适配器进程
    """
    global clasto_connection, 连续连接主程序失败次数
    服务器地址 = f"ws://{MAIN_HOST}:{MAIN_PORT}"
    
    logger.info(f"正在尝试连接到主程序: {服务器地址}")
    
    try:
        clasto_connection = await websockets.connect(
            服务器地址,
            ping_interval=None,
        )
        logger.info("成功连接到主程序")
        连续连接主程序失败次数 = 0
        return True
    except ConnectionRefusedError:
        连续连接主程序失败次数 += 1
        logger.error(f"连接主程序失败：主程序未启动或拒绝连接 (第{连续连接主程序失败次数}次)")
        if 连续连接主程序失败次数 >= 2:
            logger.error("连续2次连接主程序失败，自动关闭适配器进程")
            os._exit(1)
        return False
    except Exception as e:
        连续连接主程序失败次数 += 1
        logger.error(f"连接主程序时发生错误: 类型={type(e).__name__}, 详情={e} (第{连续连接主程序失败次数}次)")
        if 连续连接主程序失败次数 >= 2:
            logger.error("连续2次连接主程序失败，自动关闭适配器进程")
            os._exit(1)
        return False


async def 监听主程序消息():
    """
    监听来自主程序的消息（回复消息等）
    主程序断开时自动标记连接状态
    """
    global clasto_connection
    
    if not clasto_connection:
        logger.error("未连接到主程序，无法监听消息")
        return
    
    try:
        async for 原始消息 in clasto_connection:
            try:
                消息数据 = json.loads(原始消息)
                await 处理主程序消息(消息数据)
            except json.JSONDecodeError:
                logger.warning(f"收到无效的主程序消息: {原始消息[:100]}")
            except Exception as e:
                logger.error(f"处理主程序消息时出错: {e}")
    except websockets.exceptions.ConnectionClosed:
        logger.warning("与主程序的连接已断开")
        clasto_connection = None


async def 心跳检测():
    """
    心跳检测：定期检查 Napcat 是否还在线
    """
    global last_heartbeat_time
    
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        
        now = time.time()
        if last_heartbeat_time > 0 and (now - last_heartbeat_time) > (HEARTBEAT_INTERVAL * 3):
            logger.warning(f"Napcat 心跳超时 ({int(now - last_heartbeat_time)}秒未收到心跳)，可能已断开")
            break
        
        logger.debug(f"Napcat 心跳正常，距上次心跳 {int(now - last_heartbeat_time)}秒")


async def napcat连接处理(ws连接):
    """
    处理单个 Napcat 连接（正向和反向模式共用）
    """
    global napcat_connection, clasto_connection, last_heartbeat_time
    
    logger.info("napcat连接处理开始")
    
    napcat_connection = ws连接
    last_heartbeat_time = time.time()
    
    logger.info("Napcat 连接已建立")
    
    # 连接到主程序
    logger.info("步骤1: 尝试连接到主程序...")
    if not await 连接到主程序():
        logger.error("无法连接到主程序，关闭 Napcat 连接")
        await ws连接.close()
        return
    
    logger.info("步骤2: 启动监听任务...")
    # 启动主程序消息监听
    主程序监听任务 = asyncio.create_task(监听主程序消息())
    
    # 启动心跳检测任务
    心跳任务 = asyncio.create_task(心跳检测())
    
    logger.info("步骤3: 开始监听 Napcat 消息流...")
    try:
        while True:
            # 使用 wait_for 设置超时，定期检查主程序连接状态
            try:
                raw_message = await asyncio.wait_for(ws连接.recv(), timeout=5.0)
            except asyncio.TimeoutError:
                # 超时后检查主程序连接是否还活着
                if not clasto_connection or clasto_connection.state.name == 'CLOSED':
                    logger.warning("检测到主程序连接已断开，退出处理循环")
                    break
                continue
            
            logger.debug(f"收到 Napcat 原始数据: {raw_message[:200]}")
            try:
                decoded_message = json.loads(raw_message)
                # 会话筛选检查
                if 会话筛选(decoded_message):
                    await 处理napcat消息(decoded_message)
            except json.JSONDecodeError:
                logger.warning(f"收到无效的 JSON 数据: {raw_message[:100]}")
            except Exception as e:
                logger.error(f"处理 Napcat 消息时出错: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Napcat 连接已断开: code={e.code}, reason={e.reason}")
    except asyncio.CancelledError:
        logger.info("Napcat 连接处理被取消")
    except Exception as e:
        logger.exception(f"Napcat 连接处理异常: 类型={type(e).__name__}, 详情={e}")
    finally:
        logger.info("进入 finally 块，开始清理资源...")
        心跳任务.cancel()
        主程序监听任务.cancel()
        napcat_connection = None
        if clasto_connection:
            await clasto_connection.close()
            clasto_connection = None
        logger.info("Napcat 连接已清理")


# ==========================================
# 正向 WS 模式：适配器作为客户端连接 Napcat
# ==========================================

async def 正向WS连接():
    """
    正向 WS：适配器主动连接 Napcat 的 WS 服务端
    Napcat 配置中需要开启正向 WS 服务端
    """
    napcat地址 = f"ws://{NAPCAT_HOST}:{NAPCAT_PORT}"
    
    # Napcat 支持两种 token 传递方式：URL query 参数 和 Authorization header
    # 优先使用 URL query 参数（兼容性更好）
    if NAPCAT_TOKEN:
        napcat地址 += f"?access_token={NAPCAT_TOKEN}"
    
    额外头 = {}
    if NAPCAT_TOKEN:
        额外头["Authorization"] = f"Bearer {NAPCAT_TOKEN}"
    
    logger.info(f"正在连接到 Napcat: {napcat地址}")
    
    重连间隔 = 5
    while True:
        try:
            async with websockets.connect(
                napcat地址,
                additional_headers=额外头,
                max_size=2**26,  # 64MB
                ping_interval=None,  # 禁用自动 ping，避免与 Napcat 心跳冲突
            ) as ws:
                logger.info(f"成功连接到 Napcat: {napcat地址}")
                await napcat连接处理(ws)
                logger.warning("napcat连接处理函数返回，准备重连")
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Napcat 连接断开: code={e.code}, reason={e.reason}, {重连间隔}秒后重连...")
        except ConnectionRefusedError:
            logger.error(f"连接被拒绝: {napcat地址}, {重连间隔}秒后重连...")
        except Exception as e:
            logger.error(f"连接 Napcat 异常: {e}, {重连间隔}秒后重连...")
        
        await asyncio.sleep(重连间隔)


# ==========================================
# 反向 WS 模式：适配器作为服务端等待 Napcat 连接
# ==========================================

async def 检查token(conn, request):
    """
    检查 Napcat 连接的 token（仅反向模式使用）
    websockets 16.x: process_request 必须是 async 函数
    """
    if not NAPCAT_TOKEN or NAPCAT_TOKEN.strip() == "":
        return None
    auth_header = request.headers.get("Authorization")
    if auth_header != f"Bearer {NAPCAT_TOKEN}":
        return websockets.Response(
            status_code=http.HTTPStatus.UNAUTHORIZED,
            reason_phrase="Unauthorized",
            headers=websockets.Headers([("Content-Type", "text/plain")]),
            body=b"Unauthorized\n"
        )
    return None


async def 反向WS服务():
    """
    反向 WS：适配器作为服务端，等待 Napcat 反向连接
    """
    logger.info(f"正在启动反向 WS 服务，监听 {NAPCAT_HOST}:{NAPCAT_PORT}")
    logger.info(f"Token: {'已设置' if NAPCAT_TOKEN else '未设置'}")
    
    try:
        async with websockets.serve(
            napcat连接处理,
            NAPCAT_HOST,
            NAPCAT_PORT,
            max_size=2**26,
            process_request=检查token
        ):
            logger.info(f"反向 WS 服务启动成功! 监听: ws://{NAPCAT_HOST}:{NAPCAT_PORT}")
            await asyncio.Future()  # 永久运行
    except OSError as e:
        if e.errno == 10048 or "address already in use" in str(e).lower():
            logger.error(f"端口 {NAPCAT_PORT} 已被占用")
        else:
            logger.error(f"网络错误: {e}")
        raise
    except Exception as e:
        logger.error(f"反向 WS 服务启动失败: {e}")
        raise


# ==========================================
# 启动入口
# ==========================================

async def 启动napcat服务端():
    """
    根据连接模式选择启动方式
    """
    logger.info(f"连接模式: {CONNECTION_MODE}")
    logger.info(f"Napcat 地址: {NAPCAT_HOST}:{NAPCAT_PORT}")
    logger.info(f"心跳间隔: {HEARTBEAT_INTERVAL}秒")
    logger.info(f"主程序地址: {MAIN_HOST}:{MAIN_PORT}")
    
    if CONNECTION_MODE == "forward":
        await 正向WS连接()
    elif CONNECTION_MODE == "reverse":
        await 反向WS服务()
    else:
        logger.error(f"未知的连接模式: {CONNECTION_MODE}，请使用 'forward' 或 'reverse'")


async def 启动客户端():
    """
    兼容旧版启动适配器.py的调用方式
    """
    try:
        await 启动napcat服务端()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"适配器运行过程中发生错误: {e}")
    finally:
        logger.info("Napcat 适配器进程已结束。")
        os._exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(启动客户端())
    except KeyboardInterrupt:
        pass
