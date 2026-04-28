from openai import AsyncOpenAI # 导入异步 OpenAI 客户端
from 模块.log模块 import logger
from 模块.reading_config import 模型配置
import asyncio
import os
import toml

# 运行时配置（用于模型调用重试）
项目根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
运行时配置路径 = os.path.join(项目根目录, "配置文件", "runtime_config.toml")
模型调用自动重试次数 = 1  # 默认最多自动重试一次

if os.path.exists(运行时配置路径):
    try:
        with open(运行时配置路径, "r", encoding="utf-8") as f:
            运行时配置 = toml.load(f)
            模型调用自动重试次数 = int(运行时配置.get("模型调用自动重试次数", 模型调用自动重试次数))
            if 模型调用自动重试次数 < 0:
                模型调用自动重试次数 = 0
    except Exception as 错误:
        logger.warning(f"读取 runtime_config.toml 的模型重试配置失败，使用默认值1: {错误}")

# 构建模型字典缓存，将 O(n) 的线性搜索优化为 O(1) 的字典查找
# 格式: {模型名: [模型名, 厂商, 模型id, url, api_key]}
模型字典 = {模型[0]: 模型 for 模型 in 模型配置}
logger.debug(f"模型字典缓存已构建，共 {len(模型字典)} 个模型")

async def 调用模型_基础(api_key,url,模型id,user提示词,system提示词,额外参数=None): # 定义异步模型调用基础方法
    # 初始化异步客户端
    客户端 = AsyncOpenAI(
        api_key=api_key,
        base_url=url
    )
    总尝试次数 = 1 + 模型调用自动重试次数
    最后错误 = None

    if not isinstance(额外参数, dict):
        额外参数 = {}

    for 当前尝试 in range(1, 总尝试次数 + 1):
        try:
            # 使用 await 进行异步请求
            请求参数 = {
                "messages": [
                    {'role': 'system', 'content': system提示词},
                    {'role': 'user', 'content': user提示词},
                ],
                "model": 模型id,
                "stream": False,
            }
            请求参数.update({k: v for k, v in 额外参数.items() if k != "stream" and v is not None})

            响应 = await 客户端.chat.completions.create(
                **请求参数
            )
            return 响应.choices[0].message.content
        except Exception as 错误:
            最后错误 = 错误
            if 当前尝试 < 总尝试次数:
                logger.warning(
                    f"调用模型失败，准备自动重试 ({当前尝试}/{模型调用自动重试次数})，模型: {模型id}，错误: {错误}"
                )
                await asyncio.sleep(0.6)
            else:
                logger.error(f"调用模型时发生错误: {错误}")

    return f"错误：{最后错误}"

async def 调用模型(模型名,user提示词,system提示词,额外参数=None): # 定义异步模型调用包装方法
    # 使用字典查找，时间复杂度 O(1)
    模型信息 = 模型字典.get(模型名)
    if 模型信息:
        模型url = 模型信息[3] # 对应 reading_config.py 中的 url 索引
        模型id = 模型信息[2]  # 对应 reading_config.py 中的 模型id 索引
        api_key = 模型信息[4] # 对应 reading_config.py 中的 api_key 索引
        # 使用 await 调用基础方法
        return await 调用模型_基础(api_key,模型url,模型id,user提示词,system提示词,额外参数=额外参数)
    
    # 如果没找到匹配的模型
    logger.error(f"未找到名为 {模型名} 的模型配置")
    return "错误：未找到模型配置"

async def 调用模型_流式(api_key, url, 模型id, user提示词, system提示词, 额外参数=None):
    """
    流式调用模型，返回异步生成器，每次产出一段文本
    """
    客户端 = AsyncOpenAI(api_key=api_key, base_url=url)
    总尝试次数 = 1 + 模型调用自动重试次数
    最后错误 = None

    if not isinstance(额外参数, dict):
        额外参数 = {}

    for 当前尝试 in range(1, 总尝试次数 + 1):
        try:
            请求参数 = {
                "messages": [
                    {'role': 'system', 'content': system提示词},
                    {'role': 'user', 'content': user提示词},
                ],
                "model": 模型id,
                "stream": True,
            }
            请求参数.update({k: v for k, v in 额外参数.items() if k != "stream" and v is not None})

            响应流 = await 客户端.chat.completions.create(**请求参数)
            async for 片段 in 响应流:
                try:
                    if not 片段.choices:
                        continue
                    内容 = 片段.choices[0].delta.content
                    if 内容:
                        logger.debug(f"[流式] 收到片段: {repr(内容[:50])}")
                        yield 内容
                except (IndexError, AttributeError, TypeError):
                    continue
            return
        except Exception as 错误:
            最后错误 = 错误
            if 当前尝试 < 总尝试次数:
                logger.warning(
                    f"流式调用模型失败，准备自动重试 ({当前尝试}/{模型调用自动重试次数})，模型: {模型id}，错误: {错误}"
                )
                await asyncio.sleep(0.6)
            else:
                logger.error(f"流式调用模型时发生错误: {错误}")

    raise RuntimeError(f"流式调用模型失败，重试{模型调用自动重试次数}次后仍然失败: {最后错误}")

async def 调用模型流式(模型名, user提示词, system提示词, 额外参数=None):
    """
    流式调用模型包装方法，返回异步生成器
    """
    # 使用字典查找，时间复杂度 O(1)
    模型信息 = 模型字典.get(模型名)
    if 模型信息:
        模型url = 模型信息[3]
        模型id = 模型信息[2]
        api_key = 模型信息[4]
        async for 片段 in 调用模型_流式(api_key, 模型url, 模型id, user提示词, system提示词, 额外参数=额外参数):
            yield 片段
        return
    
    logger.error(f"未找到名为 {模型名} 的模型配置")
    raise RuntimeError(f"未找到名为 {模型名} 的模型配置")

if __name__ == "__main__": 
    async def 测试():
        """
        测试模型调用逻辑（仅在作为main运行时有效）
        """
        print("开始测试异步调用模型逻辑：")
        # 这里我们尝试调用配置中的第一个模型进行测试
        if len(模型配置) > 0:
            测试模型名 = 模型配置[0][0]
            print(f"正在测试模型: {测试模型名}")
            结果 = await 调用模型(
                模型名=测试模型名,
                user提示词="你好,你是谁？",
                system提示词="你是一个乐于助人的智能助手，你叫麦麦"
            )
            print(f"模型回复: {结果}")
        else:
            print("没有可用的模型配置进行测试")
    
    # 运行异步测试
    asyncio.run(测试())
