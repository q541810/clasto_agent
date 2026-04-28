# ==========================================
# 程序主入口 (main.py)
# 功能：协调各个模块，启动应用程序
# ==========================================
clasto_logo=r'''
 ██████╗██╗      █████╗ ███████╗████████╗ ██████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔════╝██║     ██╔══██╗██╔════╝╚══██╔══╝██╔═══██╗    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
██║     ██║     ███████║███████╗   ██║   ██║   ██║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██║     ██║     ██╔══██║╚════██║   ██║   ██║   ██║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
╚██████╗███████╗██║  ██║███████║   ██║   ╚██████╔╝    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
 ╚═════╝╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝    ╚═════╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
                                                                                                             
'''
print(clasto_logo)
print("--- Clasto Agent 正在启动 ---")
try:
    import sys
    # 彩蛋
    from 模块.小彩蛋 import 小彩蛋
    小彩蛋()

    import asyncio # 导入异步库
    import websockets # 导入 WebSocket 库
    import json
    import os
    from 模块.log模块 import logger # 导入日志模块
    from 模块.版本 import 程序版本, 配置文件版本 # 导入版本信息
    from 模块.openai格式模型调用 import 调用模型
    from 模块.reading_config import 模型配置, 配置内容 # 读取配置文件
    from 模块.配置管理器 import 获取配置管理器
    from 模块.配置验证器 import 验证配置并退出如果有错误
    from 模块.应用状态 import 获取应用状态
    from 模块.启动适配器 import 启动适配器
    from 模块.聊天管理器 import 聊天管理器
    from 模块.聊天管理器 import 设置插件管理器 as _设置聊天管理器插件
    from 模块.插件管理器 import 插件管理器
except ImportError as 导入错误:
    #由于这里出现错误时logger大概率还未初始化，所以使用print
    print(f"导入模块时发生致命错误,请检查运行环境或配置文件: {导入错误}")
    exit(1)

# 打印版本信息
logger.info(f"Clasto Agent 版本: {程序版本}")

# 验证配置文件
配置管理器实例 = 获取配置管理器()

# 检查配置文件版本
运行时配置 = 配置管理器实例.获取运行时配置()
配置中的版本 = 运行时配置.get("配置文件版本", "未知")

if 配置中的版本 != 配置文件版本:
    logger.warning(f"配置文件版本不匹配！程序期望: {配置文件版本}, 配置文件: {配置中的版本}")
    logger.warning("建议从 配置文件模板/ 目录更新配置文件，或在配置文件顶部添加: 配置文件版本 = \"{配置文件版本}\"")

if not 验证配置并退出如果有错误(配置管理器实例):
    logger.error(f"配置验证失败 - 程序版本: {程序版本}, 配置文件版本: {配置中的版本}")
    print("\n请修复配置文件后重新启动程序")
    exit(1)

调试模式 = "-debug" in sys.argv

if 调试模式:
    from 模块.log模块 import 设置调试模式
    设置调试模式()

# 创建应用状态实例（单例模式）
应用 = 获取应用状态(调试模式=调试模式)

# 初始化管理器
应用.设置聊天管理器(聊天管理器(调试模式=调试模式))
应用.设置插件管理器(插件管理器())
应用.设置配置管理器(配置管理器实例)
_设置聊天管理器插件(应用.插件管理器)

async def 连接状态检查():
    """
    定期检查适配器连接状态
    """
    while True:
        await asyncio.sleep(5)
        if 应用.适配器已连接:
            #logger.debug(f"适配器连接正常: {应用.适配器连接地址}")  好他妈吵，我先注释掉了
            pass
        else:
            logger.error("适配器未连接!")

async def 消息处理回调(websocket):
    """
    处理 WebSocket 连接并接收消息
    """
    应用.设置适配器连接(websocket, websocket.remote_address)
    try:
        async for 原始消息 in websocket:
            logger.debug(f"从适配器接收到原始数据: {原始消息}")
            try:
                消息数据 = json.loads(原始消息)
                if "echo" in 消息数据 and "adapter" not in 消息数据:
                    await 应用.处理API响应(消息数据)
                    continue
            except json.JSONDecodeError:
                pass
            await 应用.消息队列.put(原始消息)
    except asyncio.CancelledError:
        logger.info(f"适配器连接被取消: {应用.适配器连接地址}")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"适配器断开连接: {应用.适配器连接地址}")
    finally:
        应用.断开适配器连接()


async def 发送回复到适配器(回复数据: dict):
    """
    将AI回复通过 WebSocket 发送回适配器
    （保留此函数用于向后兼容）
    """
    return await 应用.发送回复到适配器(回复数据)

async def 调用适配器API(action: str, params: dict, timeout: int = 15) -> dict:
    """
    通过适配器调用Napcat API，等待响应
    （保留此函数用于向后兼容）
    """
    return await 应用.调用适配器API(action, params, timeout)

async def 定时批处理任务():
    """
    每1秒从消息队列中批量取出消息，放入待处理队列
    使用异步等待，不会阻塞其他任务
    """
    while True:
        消息批次 = []
        # 非阻塞地取出队列中所有可用消息
        while not 应用.消息队列.empty():
            try:
                消息 = 应用.消息队列.get_nowait()
                消息批次.append(消息)
            except asyncio.QueueEmpty:
                break
        
        if 消息批次:
            logger.debug(f"检测到 {len(消息批次)} 条待处理消息")
            for 消息 in 消息批次:
                await 应用.待处理队列.put(消息)
        
        # 异步等待1秒，不会阻塞线程
        await asyncio.sleep(1)

async def 处理待处理队列():
    """
    从待处理队列中取出消息并分发到聊天管理器
    """
    while True:
        原始消息 = await 应用.待处理队列.get()
        try:
            消息数据 = json.loads(原始消息)
            logger.debug(f"解析消息: 适配器={消息数据.get('adapter')}, 聊天ID={消息数据.get('chat_id')}")

            if 应用.插件管理器:
                消息数据 = await 应用.插件管理器.触发过滤钩子("on_message_receive", 消息数据)
                if 消息数据 is None:
                    logger.info(f"[插件系统] 消息被 on_message_receive 钩子拦截")
                    应用.待处理队列.task_done()
                    continue

            await 应用.聊天管理器.分发消息(消息数据)
        except json.JSONDecodeError:
            logger.warning(f"消息格式无效，跳过: {原始消息}")
        except Exception as 错误:
            logger.error(f"处理消息时出错: {错误}")
        finally:
            应用.待处理队列.task_done()

async def 启动WS服务():
    """
    启动 WebSocket 服务端
    """
    async with websockets.serve(消息处理回调, "localhost", 8081):
        logger.info("WebSocket 服务端已在 ws://localhost:8081 启动")
        await asyncio.Future()  # 运行直到被取消

def 检查端口占用():
    """
    检查端口 8081 是否已被占用
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", 8081))
            return False
        except OSError:
            return True

async def 运行主程序():
    """主程序"""
    
    # 检查配置内容是否成功读取
    if not 配置内容:
        logger.warning("警告：未能读取到任何有效的配置信息，程序可能无法正常工作。")
    
    # 初始化并加载插件系统
    logger.info("[插件系统] 正在扫描并加载插件...")
    await 应用.插件管理器.扫描并加载所有插件()
    已加载列表 = 应用.插件管理器.获取已加载插件列表()
    if 已加载列表:
        for 插件信息 in 已加载列表:
            logger.info(f"[插件系统] 已加载: {插件信息['name']} v{插件信息['version']} - {插件信息['description']}")
    钩子统计 = 应用.插件管理器.获取钩子统计()
    if 钩子统计:
        logger.info(f"[插件系统] 钩子注册统计: {钩子统计}")
    
    # 在后台启动 WebSocket 服务端
    服务任务 = asyncio.create_task(启动WS服务())
    
    # 启动连接状态检查任务
    状态检查任务 = asyncio.create_task(连接状态检查())
    
    # 启动定时批处理任务，每1秒从消息队列取出消息放入待处理队列
    批处理任务 = asyncio.create_task(定时批处理任务())
    
    # 启动待处理队列的消费者
    处理任务 = asyncio.create_task(处理待处理队列())
    
    # 执行适配器启动逻辑
    启动适配器()
    
    print("--- 启动流程执行完毕 ---")

    # 启动各个组件
    try:
        logger.info("主程序正在运行，等待来自适配器的消息...")
        # 等待所有后台任务运行
        await asyncio.gather(服务任务, 状态检查任务, 批处理任务, 处理任务)
    except asyncio.CancelledError:
        logger.info("正在停止消息接收循环...")
    except Exception as 异常:
        logger.error(f"程序运行过程中发生错误: {异常}")
    finally:
        logger.info("clasto agent优雅退出中....")
        # 向适配器发送关闭信号
        if 应用.适配器WS连接:
            try:
                await 应用.适配器WS连接.send(json.dumps({"action": "shutdown"}, ensure_ascii=False))
                logger.info("已向适配器发送关闭信号")
            except Exception as e:
                logger.warning(f"向适配器发送关闭信号失败: {e}")
        # 清理工作
        服务任务.cancel()
        状态检查任务.cancel()
        批处理任务.cancel()
        处理任务.cancel()
        await 应用.插件管理器.卸载所有插件()
        await 应用.聊天管理器.停止所有()
        logger.info("clasto agent优雅退出完毕~")

# 确保只有在直接运行 main.py 时才执行以下逻辑
if __name__ == "__main__":
    if 检查端口占用():
        print("错误: 端口 8081 已被占用，请检查是否已有主程序在运行")
        exit(1)
    
    try:
        # 使用 asyncio.run 开启整个程序的异步引擎
        asyncio.run(运行主程序())
    except KeyboardInterrupt:
        # 优雅处理用户手动停止程序 (Ctrl+C)
        logger.warning("检测到用户中断，程序正在退出...")
    except Exception as 致命错误:
        # 捕获并记录所有未处理的异常
        logger.exception(f"程序运行过程中发生致命错误: {致命错误}")



#                       _oo0oo_
#                      o8888888o
#                      88" . "88
#                      (| -_- |)
#                      0\  =  /0
#                    ___/`---'\___
#                  .' \\|     |// '.
#                 / \\|||  :  |||// \
#                / _||||| -:- |||||- \
#               |   | \\\  -  /// |   |
#               | \_|  ''\---/''  |_/ |
#               \  .-\__  '-'  ___/-. /
#             ___'. .'  /--.--\  `. .'___
#          ."" '<  `.___\_<|>_/___.' >' "".
#         | | :  `- \`.;`\ _ /`;.`/ - ` : | |
#         \  \ `_.   \_ __\ /__ _/   .-` /  /
#     =====`-.____`.___ \_____/___.-`___.-'=====
#                       `=---='
#
#
#     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#             佛祖保佑佑佑佑   永无BUGGGG
