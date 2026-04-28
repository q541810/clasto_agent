# ==========================================
# 工具执行器 (工具执行器.py)
# 功能：定义可用工具，执行规划模型输出的工具调用
# ==========================================
import json
import re
import asyncio
import html
import urllib.parse
import urllib.request
from 模块.log模块 import logger
from 模块.openai格式模型调用 import 调用模型, 调用模型流式
from 模块.配置管理器 import 获取配置管理器

# 使用统一的配置管理器
配置管理器 = 获取配置管理器()
回复模型配置 = 配置管理器.获取回复模型配置()


class 工具注册表:
    """
    工具注册表，管理所有可用工具
    """
    _工具 = {}
    _别名 = {}
    _元信息 = {}

    @classmethod
    def 注册(cls, 名称, 工具函数, 别名=None, 参数说明=None, 说明="", 是否回复工具=False):
        cls._工具[名称] = 工具函数
        if 别名:
            for 别名 in 别名:
                cls._别名[别名] = 名称
        cls._元信息[名称] = {
            "参数说明": 参数说明 or {},
            "说明": 说明,
            "别名": 别名 or [],
            "是否回复工具": 是否回复工具,
        }

    @classmethod
    def 获取(cls, 名称):
        if 名称 in cls._工具:
            return cls._工具[名称]
        真实名称 = cls._别名.get(名称)
        if 真实名称:
            return cls._工具[真实名称]
        return None

    @classmethod
    def 获取所有工具描述(cls) -> str:
        描述列表 = []
        for 名称, 函数 in cls._工具.items():
            描述列表.append(函数.工具描述 if hasattr(函数, "工具描述") else f"{名称} - 无描述")
        return "\n".join(描述列表)

    @classmethod
    def 获取规划工具元信息(cls) -> dict:
        return cls._元信息


def 工具描述(描述: str):
    """装饰器：为工具函数添加描述属性"""
    def 装饰器(函数):
        函数.工具描述 = 描述
        return 函数
    return 装饰器


def 生成规划system提示词(基础提示词: str = "") -> str:
    元信息 = 工具注册表.获取规划工具元信息()
    if not 元信息:
        return 基础提示词 or "你是一个对话规划器。"

    工具行 = []
    索引 = 1
    for 工具名, 信息 in 元信息.items():
        参数说明 = 信息.get("参数说明", {})
        参数文本 = "无"
        if 参数说明:
            参数文本 = "、".join([f"{k}（{v}）" for k, v in 参数说明.items()])
        工具行.append(f"{索引}. {工具名} - {信息.get('说明', '')}。参数：{参数文本}")
        索引 += 1

    if not 基础提示词.strip():
        基础提示词 = "你是一个对话规划器。你的职责是分析用户消息，决定需要调用哪些工具来处理这条消息。"

    固定规则 = (
        "输出格式：必须输出纯JSON，格式为 {\"tool_calls\": [{\"name\": \"工具名\", \"parameters\": {\"参数名\": \"参数值\"}}]}\n\n"
        "规则：\n"
        "- JSON 必须使用英文半角标点，尤其是冒号必须是 ':'，不能是全角 '：'\n"
        "- 如果需要回复用户，必须调用回复工具\n"
        "- 对于无意义/噪声/无需响应的消息，可调用 不回复工具 或输出空工具列表\n"
        "- 可以同时调用多个工具，将多个工具放在同一个 tool_calls 数组中\n"
        "- chat_type 只能使用 'group' 或 'private'\n"
        "- 回复工具的 备注 仅用于补充上下文，不要复述用户原话，不要写无意义套话\n"
        "- 需要继续下一轮规划时，必须调用 多轮执行工具，不能用 回复工具 备注 代替\n"
        "- 如果不需要任何操作，输出 {\"tool_calls\": []}\n"
        "- 不许编造不存在的工具\n\n"
        "示例1 - 单次调用一个工具：\n"
        "输入：[用户]你好\n"
        "输出：{\"tool_calls\": [{\"name\": \"回复工具\", \"parameters\": {}}]}\n"
        "错误：{\"tool_calls\": [{\"name\": \"回复工具\", \"parameters：\": {}}]}\n\n"
        "示例2 - 单次调用多个工具：\n"
        "输入：[用户]你可以向群聊1064277981发一个\"test\"吗\n"
        "输出：{\"tool_calls\": [{\"name\": \"发送消息工具\", \"parameters\": {\"chat_id\": \"1064277981\", \"chat_type\": \"group\", \"message\": \"test\"}}, {\"name\": \"回复工具\", \"parameters\": {}}]}\n\n"
        "示例3 - 查询信息后再回复：\n"
        "输入：[用户]现在几点了\n"
        "输出：{\"tool_calls\": [{\"name\": \"获取当前时间工具\", \"parameters\": {}}, {\"name\": \"回复工具\", \"parameters\": {\"备注\": \"已获取当前时间，直接告诉用户时间并简短回答\"}}]}\n\n"
        "示例4 - 防止滥用备注：\n"
        "输入：[用户]你好\n"
        "错误示例：{\"tool_calls\": [{\"name\": \"回复工具\", \"parameters\": {\"备注\": \"用户说你好，请回复你好\"}}]}\n"
        "正确示例：{\"tool_calls\": [{\"name\": \"回复工具\", \"parameters\": {}}]}\n\n"
        "示例5 - 多轮执行1：\n"
        "输入：[用户]先查下今天北京时间，再联网搜一下今天科技热点，最后给我一句总结\n"
        "第一轮输出：{\"tool_calls\": [{\"name\": \"获取当前时间工具\", \"parameters\": {}}, {\"name\": \"多轮执行工具\", \"parameters\": {\"备注\": \"已拿到当前时间，下一轮请执行联网搜索并最终回复\"}}]}\n"
        "第二轮输出示例：{\"tool_calls\": [{\"name\": \"联网搜索工具\", \"parameters\": {\"query\": \"今日 科技 热点\", \"count\": 5}}, {\"name\": \"回复工具\", \"parameters\": {\"备注\": \"已完成时间与热点搜索，请整合为一句简要总结\"}}]}\n\n"
        "示例6 - 多轮执行2：\n"
        "输入：[用户]请在objk1这个群里发送消息\n"
        "错误示例：{\"tool_calls\": [{\"name\": \"回复工具\", \"parameters\": {\"备注\": \"需要先查群列表，进入下一轮\"}}]}\n"
        "正确示例：{\"tool_calls\": [{\"name\": \"查询群列表工具\", \"parameters\": {}}, {\"name\": \"多轮执行工具\", \"parameters\": {\"备注\": \"已获得群列表，下一轮根据群名匹配chat_id后发送消息并回复\"}}]}\n\n"
        "示例7 - 可选择不回复：\n"
        "输入：[用户]....\n"
        "输出：{\"tool_calls\": [{\"name\": \"不回复工具\", \"parameters\": {\"原因\": \"无意义消息\"}}]}"
    )

    return f"{基础提示词.strip()}\n\n可用工具：\n" + "\n".join(工具行) + "\n\n" + 固定规则


@工具描述("回复工具 - 进入回复阶段，将当前消息交由回复模型生成回复。参数：备注(可选，补充上下文)")
async def 回复工具(**参数):
    """
    回复工具：调用回复模型生成回复，并发送回原会话
    """
    聊天流 = 参数.get("_聊天流")
    消息 = 参数.get("_消息")
    仅生成不发送 = bool(参数.get("_仅生成不发送", False))
    if not 聊天流 or not 消息:
        logger.error("回复工具缺少聊天流或消息参数")
        return {"status": "error", "message": "缺少必要参数"}

    模型名 = 回复模型配置.get("model", "")
    if not 模型名:
        logger.warning("未配置回复模型")
        return {"status": "error", "message": "未配置回复模型"}

    system提示词 = 回复模型配置.get("system_prompt", "你是一个乐于助人的AI助手。")
    额外参数 = dict(回复模型配置.get("额外参数", {}))

    备注 = str(参数.get("备注", "")).strip()
    if 备注:
        聊天流.对话历史.append({"role": "system", "content": f"[规划备注] {备注}"})

    对话内容 = "\n".join([f"{m['role']}: {m['content']}" for m in 聊天流.对话历史])

    from 模块.聊天管理器 import _插件管理器实例 as _pm_instance, 回复逻辑配置
    if _pm_instance:
        钩子结果 = await _pm_instance.触发钩子(
            "on_pre_reply",
            聊天流=聊天流,
            system提示词=system提示词,
            user提示词=对话内容,
        )
        if 钩子结果:
            if 钩子结果.get("system提示词") is not None:
                system提示词 = 钩子结果["system提示词"]
            if 钩子结果.get("user提示词") is not None:
                对话内容 = 钩子结果["user提示词"]

    if 聊天流.调试模式:
        logger.debug(f"[调试模式] 回复模型输入:\n=== System Prompt ===\n{system提示词}\n=== User Prompt ===\n{对话内容}\n=== End ===")

    分割器启用 = bool(回复逻辑配置.get("消息分割器", {}).get("启用", False))

    if 分割器启用:
        if 额外参数.get("stream") is not None:
            logger.warning("[消息分割器] 启用消息分割器后将忽略回复模型的stream参数")
            额外参数.pop("stream", None)
        try:
            模型回复 = await 聊天流._流式分割发送(模型名, 对话内容, system提示词, 额外参数)
        except Exception as e:
            logger.error(f"流式调用回复模型失败: {e}")
            return {"status": "error", "message": f"流式调用失败: {e}"}
        if _pm_instance and 模型回复:
            模型回复 = await _pm_instance.触发修改钩子("on_post_reply", 模型回复)
        if not 仅生成不发送:
            聊天流.对话历史.append({"role": "assistant", "content": 模型回复})
        return {"status": "success", "message": 模型回复}

    模型回复 = await 调用模型(
        模型名=模型名,
        user提示词=对话内容,
        system提示词=system提示词,
        额外参数=额外参数
    )

    if 模型回复 and not 模型回复.startswith("错误"):
        from 模块.聊天管理器 import _插件管理器实例 as _pm_instance2
        if _pm_instance2 and 模型回复:
            模型回复 = await _pm_instance2.触发修改钩子("on_post_reply", 模型回复)
        if not 仅生成不发送:
            聊天流.对话历史.append({"role": "assistant", "content": 模型回复})
            await 聊天流._发送回复(模型回复)
        return {"status": "success", "message": 模型回复}
    else:
        logger.error(f"回复模型调用失败: {模型回复}")
        return {"status": "error", "message": 模型回复}


@工具描述("不回复工具 - 明确本轮不回复用户。参数：原因(可选)")
async def 不回复工具(**参数):
    """
    不回复工具：用于无意义消息、噪声消息等场景，明确跳过回复
    """
    原因 = str(参数.get("原因", "")).strip()
    if 原因:
        return {"status": "success", "message": f"本轮不回复，原因: {原因}"}
    return {"status": "success", "message": "本轮不回复"}


@工具描述("发送消息工具 - 直接向指定会话发送消息。参数：chat_id（目标会话ID）、chat_type（group/private）、message（消息内容）")
async def 发送消息工具(**参数):
    """
    发送消息工具：直接向指定会话发送消息
    """
    chat_id = 参数.get("chat_id")
    chat_type = 参数.get("chat_type", "group")
    message = 参数.get("message", "")

    if not chat_id or not message:
        logger.error("发送消息工具缺少chat_id或message参数")
        return {"status": "error", "message": "缺少必要参数"}

    import sys
    _main = sys.modules.get("main") or sys.modules.get("__main__")
    if not _main or not hasattr(_main, "发送回复到适配器"):
        logger.error("无法获取发送函数")
        return {"status": "error", "message": "无法获取发送函数"}

    回复数据 = {
        "action": "send_message",
        "chat_type": chat_type,
        "chat_id": chat_id,
        "message": message,
    }

    成功 = await _main.发送回复到适配器(回复数据)
    if 成功:
        logger.info(f"发送消息工具已发送 [{chat_id}]: {message[:50]}")
        return {"status": "success", "message": "消息已发送"}
    else:
        logger.error(f"发送消息工具发送失败 [{chat_id}]")
        return {"status": "error", "message": "发送失败"}


@工具描述("获取当前时间工具 - 获取当前系统时间。参数：无")
async def 获取当前时间工具(**参数):
    """
    获取当前时间工具：返回当前系统时间
    """
    from datetime import datetime
    当前时间 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    星期 = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    当前星期 = 星期[datetime.now().weekday()]
    return {"status": "success", "data": {"时间": 当前时间, "星期": 当前星期}, "message": f"当前时间: {当前时间} {当前星期}"}


@工具描述("查询群列表工具 - 查询当前账号已加入的所有群聊。参数：无")
async def 查询群列表工具(**参数):
    """
    查询群列表工具：通过Napcat API获取已加入的所有群聊
    """
    import sys
    _main = sys.modules.get("main") or sys.modules.get("__main__")
    if not _main or not hasattr(_main, "调用适配器API"):
        logger.error("无法获取API调用函数")
        return {"status": "error", "message": "无法获取API调用函数"}

    结果 = await _main.调用适配器API("get_group_list", {})
    
    if 结果.get("status") == "ok" or 结果.get("retcode") == 0:
        群列表 = 结果.get("data", [])
        群信息 = []
        for 群 in 群列表:
            群信息.append({"群号": 群.get("group_id"), "群名称": 群.get("group_name", "未知")})
        logger.info(f"查询群列表成功，共 {len(群信息)} 个群")
        return {"status": "success", "data": 群信息, "message": f"共查询到 {len(群信息)} 个群"}
    else:
        logger.error(f"查询群列表失败: {结果}")
        return {"status": "error", "message": 结果.get("message", "查询失败")}


@工具描述("获取会话消息工具 - 获取某个群聊或私聊的最近消息。参数：条数(可选，默认5，上限30)、chat_id(可选)、chat_type(可选)")
async def 获取会话消息工具(**参数):
    """
    获取会话消息工具：从聊天管理器读取指定会话最近消息
    """
    聊天流 = 参数.get("_聊天流")
    if not 聊天流:
        return {"status": "error", "message": "缺少当前会话上下文"}

    条数 = 参数.get("条数", 5)
    try:
        条数 = int(条数)
    except Exception:
        条数 = 5
    条数 = max(1, min(条数, 30))

    目标chat_id = str(参数.get("chat_id", "")).strip()
    目标chat_type = str(参数.get("chat_type", "")).strip()

    if not 目标chat_id:
        目标chat_id = 聊天流.chat_id
        目标chat_type = 聊天流.chat_type
    else:
        if 目标chat_id.startswith("group_"):
            目标chat_type = "group"
        elif 目标chat_id.startswith("private_"):
            目标chat_type = "private"
        elif 目标chat_type in ("group", "private"):
            前缀 = "group_" if 目标chat_type == "group" else "private_"
            目标chat_id = f"{前缀}{目标chat_id}"
        else:
            return {"status": "error", "message": "chat_id 不带前缀时必须提供 chat_type(group/private)"}

    import sys
    _main = sys.modules.get("main") or sys.modules.get("__main__")
    if not _main or not hasattr(_main, "管理器"):
        return {"status": "error", "message": "无法获取聊天管理器"}

    管理器 = _main.管理器
    目标聊天流 = 管理器.聊天流字典.get(目标chat_id)
    if not 目标聊天流:
        return {
            "status": "success",
            "message": "目标会话暂无消息记录",
            "data": {"chat_id": 目标chat_id, "chat_type": 目标chat_type or "unknown", "count": 0, "messages": []}
        }

    历史片段 = 目标聊天流.对话历史[-条数:]
    消息列表 = []
    for 项 in 历史片段:
        消息列表.append({
            "role": 项.get("role", "unknown"),
            "content": 项.get("content", "")
        })

    return {
        "status": "success",
        "message": f"已获取 {len(消息列表)} 条消息",
        "data": {
            "chat_id": 目标chat_id,
            "chat_type": 目标聊天流.chat_type,
            "count": len(消息列表),
            "messages": 消息列表
        }
    }


@工具描述("联网搜索工具 - 使用公开网页结果进行联网搜索（无需API Key）。参数：query(搜索关键词)、count(返回条数，可选，默认5)")
async def 联网搜索工具(**参数):
    """
    联网搜索工具：通过 Bing 公开搜索页抓取结果（无需API Key）
    """
    query = str(参数.get("query", "")).strip()
    count = 参数.get("count", 5)

    if not query:
        return {"status": "error", "message": "缺少 query 参数"}

    try:
        count = int(count)
    except Exception:
        count = 5
    count = max(1, min(count, 10))

    query_str = urllib.parse.urlencode({"q": query, "count": count, "setlang": "zh-hans", "format": "rss"})
    请求URL = f"https://www.bing.com/search?{query_str}"

    请求对象 = urllib.request.Request(
        请求URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml,application/xml,text/xml,text/html"
        },
        method="GET"
    )

    def _执行请求():
        with urllib.request.urlopen(请求对象, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    try:
        html内容 = await asyncio.to_thread(_执行请求)
    except Exception as e:
        logger.error(f"联网搜索失败: {e}")
        return {"status": "error", "message": f"联网搜索失败: {e}"}

    结果列表 = []

    try:
        import xml.etree.ElementTree as ET
        根 = ET.fromstring(html内容)
        for 项 in 根.findall("./channel/item")[:count]:
            标题 = (项.findtext("title") or "").strip()
            链接 = (项.findtext("link") or "").strip()
            摘要 = (项.findtext("description") or "").strip()
            if 标题 and 链接:
                结果列表.append({"标题": 标题, "链接": 链接, "摘要": 摘要})
    except Exception:
        pass

    if not 结果列表:
        正则列表 = [
            r'<li class="b_algo".*?<h2><a href="(.*?)"[^>]*>(.*?)</a></h2>.*?<p>(.*?)</p>',
            r'<h2><a href="(https?://[^\"]+)"[^>]*>(.*?)</a></h2>.*?<p>(.*?)</p>',
            r'<a href="(https?://[^\"]+)" h="ID=SERP,[^\"]+"[^>]*>(.*?)</a>.*?<div class="b_caption"><p>(.*?)</p>'
        ]
        for 正则 in 正则列表:
            网页结果 = re.findall(正则, html内容, re.DOTALL)
            if 网页结果:
                for 链接, 标题, 摘要 in 网页结果[:count]:
                    纯标题 = html.unescape(re.sub(r"<.*?>", "", 标题).strip())
                    纯摘要 = html.unescape(re.sub(r"<.*?>", "", 摘要).strip())
                    if 纯标题 and 链接:
                        结果列表.append({"标题": 纯标题, "链接": 链接, "摘要": 纯摘要})
                break

    return {
        "status": "success",
        "message": f"联网搜索完成，共 {len(结果列表)} 条结果",
        "data": {
            "query": query,
            "results": 结果列表
        }
    }


@工具描述("多轮执行工具 - 请求进入下一轮规划。参数：备注(可选，说明下一轮要点)")
async def 多轮执行工具(**参数):
    """
    多轮执行工具：标记需要继续进行下一轮规划
    """
    备注 = str(参数.get("备注", "")).strip()
    return {
        "status": "success",
        "message": "已请求进入下一轮规划",
        "data": {"备注": 备注}
    }


def 注册内置工具():
    """注册所有内置工具"""
    工具注册表.注册(
        "回复工具",
        回复工具,
        别名=["回复", "回复工具"],
        参数说明={"备注": "可选，给回复模型的额外上下文说明，仅在必要时使用，禁止重复用户原话"},
        说明="进入回复阶段，调用回复模型生成回复",
        是否回复工具=True,
    )
    工具注册表.注册(
        "不回复工具",
        不回复工具,
        别名=["不回复", "不回复工具", "跳过回复"],
        参数说明={"原因": "可选，不回复原因"},
        说明="明确本轮不回复用户",
    )
    工具注册表.注册(
        "发送消息工具",
        发送消息工具,
        别名=["发送消息", "发送消息工具", "发消息"],
        参数说明={"chat_id": "目标会话ID", "chat_type": "必须是 'group' 或 'private'", "message": "消息内容"},
        说明="直接向指定会话发送消息",
    )
    工具注册表.注册(
        "查询群列表工具",
        查询群列表工具,
        别名=["查询群列表", "查询群列表工具", "查群", "群列表"],
        参数说明={},
        说明="查询当前账号已加入的所有群聊，返回群号和群名称",
    )
    工具注册表.注册(
        "获取会话消息工具",
        获取会话消息工具,
        别名=["获取会话消息", "获取会话消息工具", "查询消息", "消息记录"],
        参数说明={"条数": "可选，默认5，上限30", "chat_id": "可选，目标会话ID，默认当前会话", "chat_type": "可选，group/private；chat_id不带前缀时必填"},
        说明="获取某个群聊或私聊最近消息",
    )
    工具注册表.注册(
        "获取当前时间工具",
        获取当前时间工具,
        别名=["获取当前时间", "获取当前时间工具", "获取时间", "查时间", "时间"],
        参数说明={},
        说明="获取当前系统时间和星期",
    )
    工具注册表.注册(
        "联网搜索工具",
        联网搜索工具,
        别名=["联网搜索", "联网搜索工具", "搜索", "bing搜索"],
        参数说明={"query": "搜索关键词", "count": "返回条数，可选，默认5"},
        说明="使用Bing公开搜索页进行联网搜索(无需API)",
    )
    工具注册表.注册(
        "多轮执行工具",
        多轮执行工具,
        别名=["多轮执行", "多轮执行工具", "继续规划", "继续执行"],
        参数说明={"备注": "可选，说明下一轮规划重点"},
        说明="请求进入下一轮规划，并携带额外上下文",
    )


async def 执行工具调用(工具调用: dict, 聊天流, 消息: dict) -> dict:
    """
    执行单个工具调用
    """
    工具名 = 工具调用.get("name", "")
    工具参数 = dict(工具调用.get("parameters", {}) or {})

    工具函数 = 工具注册表.获取(工具名)
    if not 工具函数:
        logger.warning(f"未知工具: {工具名}")
        return {"status": "error", "message": f"未知工具: {工具名}"}

    工具参数["_聊天流"] = 聊天流
    工具参数["_消息"] = 消息

    try:
        结果 = await 工具函数(**工具参数)
        logger.info(f"工具执行完成: {工具名} -> {结果.get('status')}")
        return 结果
    except Exception as e:
        logger.error(f"工具执行失败: {工具名}, 错误: {e}")
        return {"status": "error", "message": str(e)}


def 解析规划输出(模型输出: str) -> list:
    """
    从规划模型的输出中解析工具调用列表
    支持纯JSON和包含在文本中的JSON
    """
    模型输出 = 模型输出.strip()

    try:
        数据 = json.loads(模型输出)
        if isinstance(数据, dict) and "tool_calls" in 数据:
            return 数据["tool_calls"]
        elif isinstance(数据, list):
            return 数据
    except json.JSONDecodeError:
        pass

    json匹配 = re.search(r'\{[^{}]*"tool_calls"[^{}]*\}', 模型输出, re.DOTALL)
    if json匹配:
        try:
            数据 = json.loads(json匹配.group())
            return 数据.get("tool_calls", [])
        except json.JSONDecodeError:
            pass

    logger.warning(f"无法解析规划模型输出: {模型输出[:200]}")
    return []
