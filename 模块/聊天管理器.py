# ==========================================
# 聊天管理器 (聊天管理器.py)
# 功能：管理所有聊天流，按群/私聊为单位独立处理消息
# ==========================================
import asyncio
import json
import toml
import os
from 模块.log模块 import logger
from 模块.openai格式模型调用 import 调用模型, 调用模型流式
from 模块 import 工具执行器
from 模块.插件管理器 import 插件管理器

# 读取回复模型配置
项目根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
模型配置文件路径 = os.path.join(项目根目录, "配置文件", "model_config.toml")
运行逻辑配置文件路径 = os.path.join(项目根目录, "配置文件", "runtime_config.toml")

回复模型配置 = {"model": "", "system_prompt": "", "max_history": 20, "额外参数": {}}
规划模型配置 = {"model": "", "system_prompt": "", "额外参数": {}}
筛选模型配置 = {"model": "", "system_prompt": "", "额外参数": {}}
回复逻辑配置 = {
    "bot的名字": "bot",
    "群聊": {
        "mode": "群聊回复优化",
        "关闭规划模型": False,
    },
    "私聊": {
        "mode": "直接规划",
        "关闭规划模型": False,
    },
    "群聊回复优化": {
        "原因最大字数": 30,
        "上下文条数": 7,
        "at必回复": True,
        "提及关键词": [],
    }
}
if os.path.exists(模型配置文件路径):
    try:
        with open(模型配置文件路径, "r", encoding="utf-8") as f:
            _mc = toml.load(f)
            _rm = _mc.get("回复模型", {})
            回复模型配置["model"] = _rm.get("model", "")
            回复模型配置["system_prompt"] = _rm.get("system_prompt", "")
            回复模型配置["max_history"] = _rm.get("max_history", 20)
            回复模型配置["额外参数"] = _rm.get("额外参数", {}) if isinstance(_rm.get("额外参数", {}), dict) else {}
            _pm = _mc.get("规划模型", {})
            规划模型配置["model"] = _pm.get("model", "")
            规划模型配置["system_prompt"] = _pm.get("system_prompt", "")
            规划模型配置["额外参数"] = _pm.get("额外参数", {}) if isinstance(_pm.get("额外参数", {}), dict) else {}
            _sm = _mc.get("筛选模型", {})
            筛选模型配置["model"] = _sm.get("model", "")
            筛选模型配置["system_prompt"] = _sm.get("system_prompt", "")
            筛选模型配置["额外参数"] = _sm.get("额外参数", {}) if isinstance(_sm.get("额外参数", {}), dict) else {}
        logger.info(f"回复模型配置加载成功: {回复模型配置['model']}")
        if 规划模型配置["model"]:
            logger.info(f"规划模型配置加载成功: {规划模型配置['model']}")
        else:
            logger.info("规划模型未配置，将跳过规划阶段")
        if 筛选模型配置["model"]:
            logger.info(f"筛选模型配置加载成功: {筛选模型配置['model']}")
        else:
            logger.info("筛选模型未配置，群聊回复优化将默认放行（不使用小模型筛选）")
    except Exception as e:
        logger.error(f"模型配置加载失败: {e}")
else:
    logger.warning("模型配置文件不存在，使用默认配置")

if os.path.exists(运行逻辑配置文件路径):
    try:
        with open(运行逻辑配置文件路径, "r", encoding="utf-8") as f:
            _rc = toml.load(f)
            回复逻辑配置["bot的名字"] = str(_rc.get("bot的名字", 回复逻辑配置["bot的名字"]))
            _g = _rc.get("群聊回复逻辑", {})
            _p = _rc.get("私聊回复逻辑", {})
            _go = _rc.get("群聊回复优化", {})

            回复逻辑配置["群聊"]["mode"] = _g.get("mode", 回复逻辑配置["群聊"]["mode"])
            回复逻辑配置["群聊"]["关闭规划模型"] = bool(_g.get("关闭规划模型", 回复逻辑配置["群聊"]["关闭规划模型"]))

            回复逻辑配置["私聊"]["mode"] = _p.get("mode", 回复逻辑配置["私聊"]["mode"])
            回复逻辑配置["私聊"]["关闭规划模型"] = bool(_p.get("关闭规划模型", 回复逻辑配置["私聊"]["关闭规划模型"]))

            # 兼容旧版配置：若未拆分 ["群聊回复优化"]，则回退读取 ["群聊回复逻辑"] 里的旧字段
            旧_原因最大字数 = _g.get("原因最大字数", 回复逻辑配置["群聊回复优化"]["原因最大字数"])
            旧_at必回复 = _g.get("at必回复", 回复逻辑配置["群聊回复优化"]["at必回复"])
            旧_提及关键词 = _g.get("提及关键词", 回复逻辑配置["群聊回复优化"]["提及关键词"])

            回复逻辑配置["群聊回复优化"]["原因最大字数"] = int(_go.get("原因最大字数", 旧_原因最大字数))
            回复逻辑配置["群聊回复优化"]["上下文条数"] = int(_go.get("上下文条数", 回复逻辑配置["群聊回复优化"]["上下文条数"]))
            回复逻辑配置["群聊回复优化"]["at必回复"] = bool(_go.get("at必回复", 旧_at必回复))
            回复逻辑配置["群聊回复优化"]["提及关键词"] = _go.get("提及关键词", 旧_提及关键词)

            消息分割器配置 = _rc.get("消息分割器", {})
            回复逻辑配置["消息分割器"] = {
                "启用": bool(消息分割器配置.get("启用", False)),
            }
        logger.info("回复逻辑配置加载成功")
    except Exception as e:
        logger.error(f"回复逻辑配置加载失败: {e}")
else:
    logger.warning("运行逻辑配置文件不存在，使用默认回复逻辑")

工具执行器.注册内置工具()

_插件管理器实例: 插件管理器 | None = None

def 设置插件管理器(管理器: 插件管理器):
    global _插件管理器实例
    _插件管理器实例 = 管理器

class 聊天流:
    """
    单个聊天流（一个群或一个私聊）
    每个聊天流有独立的消息队列和对话上下文
    """
    
    def __init__(self, chat_id: str, chat_type: str, adapter: str, 调试模式: bool = False):
        self.chat_id = chat_id
        self.chat_type = chat_type
        self.adapter = adapter
        self.消息队列 = asyncio.Queue()
        self.对话历史 = []  # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        self.处理状态 = "空闲"
        self.最后活跃时间 = None
        self._处理任务 = None
        self._运行中 = True
        self.调试模式 = 调试模式
        self.分割器已发送 = False
    
    async def 启动处理循环(self):
        """启动独立的消息处理循环"""
        self._处理任务 = asyncio.create_task(self._处理消息())
        logger.info(f"聊天流 [{self.chat_id}] 已启动处理循环")

    async def _群聊回复优化决策(self, 消息: dict) -> dict:
        """
        群聊回复优化：先让小模型输出简短原因，再输出是否回复
        输出格式（纯文本两行）：
        原因: <不超过N字>
        决策: 回复/不回复
        """
        配置键 = "群聊" if self.chat_type == "group" else "私聊"
        本配置 = 回复逻辑配置.get("群聊回复优化", {})
        小模型名 = 筛选模型配置.get("model", "")
        最大字数 = int(本配置.get("原因最大字数", 30))
        上下文条数 = int(本配置.get("上下文条数", 7))
        at必回复 = bool(本配置.get("at必回复", True))
        提及关键词 = 本配置.get("提及关键词", []) or []

        文本 = str(消息.get("message", ""))
        segments = 消息.get("message_segments", []) or []
        self_id = str(消息.get("self_id", ""))
        bot名字 = str(回复逻辑配置.get("bot的名字", "bot"))

        被at = False
        for 段 in segments:
            if isinstance(段, dict) and 段.get("type") == "at":
                qq = str(段.get("data", {}).get("qq", ""))
                if self_id and qq == self_id:
                    被at = True
                    break

        被关键词提及 = any(str(k) and str(k) in 文本 for k in 提及关键词)
        if at必回复 and (被at or 被关键词提及):
            return {"回复": True, "原因": "命中@或提及"}

        if not 小模型名:
            return {"回复": True, "原因": "未配置筛选模型，默认回复"}

        基础筛选提示词 = 筛选模型配置.get("system_prompt", "")
        筛选system提示词 = (
            (基础筛选提示词.strip() + "\n\n" if 基础筛选提示词.strip() else "")
            + "你是消息筛选器。只输出两行，不要JSON。\n"
            + f"当前bot名字: {bot名字}\n"
            f"第一行固定格式: 原因: <不超过{最大字数}字>\n"
            "第二行固定格式: 决策: 回复 或 决策: 不回复\n"
            "不得输出其他内容。"
        )
        筛选user提示词 = (
            f"chat_type={self.chat_type}\n"
            f"sender={消息.get('sender_name', '未知')}\n"
            f"message={文本}"
        )

        if 上下文条数 > 0 and self.对话历史:
            历史片段 = self.对话历史[-上下文条数:]
            历史文本 = "\n".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in 历史片段])
            筛选user提示词 += f"\nrecent_context:\n{历史文本}"

        if self.调试模式:
            logger.debug(f"[调试模式] 群聊回复优化输入:\n=== System Prompt ===\n{筛选system提示词}\n=== User Prompt ===\n{筛选user提示词}\n=== End ===")

        输出 = await 调用模型(
            模型名=小模型名,
            user提示词=筛选user提示词,
            system提示词=筛选system提示词,
            额外参数=筛选模型配置.get("额外参数", {})
        ) or ""
        原因 = ""
        决策回复 = True
        for 行 in 输出.splitlines():
            行 = 行.strip()
            if 行.startswith("原因:"):
                原因 = 行[3:].strip()[:最大字数]
            elif 行.startswith("决策:"):
                值 = 行[3:].strip()
                决策回复 = ("不回复" not in 值)

        return {"回复": 决策回复, "原因": 原因 or "小模型决策"}

    async def _并行群聊回复优化决策(self, 消息列表: list[dict]) -> list[dict]:
        """
        对一批消息并行执行群聊回复优化判断
        """
        任务列表 = [asyncio.create_task(self._群聊回复优化决策(单条消息)) for 单条消息 in 消息列表]
        结果列表 = await asyncio.gather(*任务列表, return_exceptions=True)
        规范结果 = []
        for 结果 in 结果列表:
            if isinstance(结果, Exception):
                logger.error(f"群聊回复优化并行判断异常: {结果}")
                规范结果.append({"回复": True, "原因": "判断异常，默认回复"})
            else:
                规范结果.append(结果)
        return 规范结果
    
    async def _处理消息(self):
        """内部消息处理循环"""
        while self._运行中:
            本轮消息数 = 0
            try:
                首条消息 = await self.消息队列.get()
                消息列表 = [首条消息]
                本轮消息数 = 1
                消息 = 消息列表[-1]
                self.处理状态 = "处理中"

                开始时间 = asyncio.get_event_loop().time()
                截止时间 = 开始时间 + 3.0
                待发送回复 = ""
                跳过回复 = False

                while True:
                    规划结果 = {"回复内容": "", "跳过回复": False, "可继续合并": True}
                    配置键 = "群聊" if self.chat_type == "group" else "私聊"
                    回复模式 = 回复逻辑配置.get(配置键, {}).get("mode", "直接规划")
                    关闭规划模型 = bool(回复逻辑配置.get(配置键, {}).get("关闭规划模型", False))

                    需要进入规划 = True
                    筛选原因 = ""
                    if 回复模式 in ("群聊回复优化", "二阶段筛选"):
                        if len(消息列表) > 1:
                            logger.info(f"聊天流 [{self.chat_id}] 对 {len(消息列表)} 条消息并行执行群聊回复优化判断")
                        判断结果列表 = await self._并行群聊回复优化决策(消息列表)
                        需处理消息列表 = [m for m, r in zip(消息列表, 判断结果列表) if bool(r.get("回复", True))]
                        需要进入规划 = len(需处理消息列表) > 0
                        if not 需要进入规划:
                            原因摘要 = "; ".join([str(r.get("原因", "")) for r in 判断结果列表 if r.get("原因")])
                            筛选原因 = 原因摘要[:200]
                            self.对话历史.append({"role": "system", "content": f"[筛选决策] 不回复，原因: {筛选原因}"})
                            规划结果 = {"回复内容": "", "跳过回复": True, "可继续合并": True}
                        else:
                            if len(需处理消息列表) < len(消息列表):
                                logger.info(f"聊天流 [{self.chat_id}] 并行判断后保留 {len(需处理消息列表)}/{len(消息列表)} 条进入规划")
                            消息列表 = 需处理消息列表
                            消息 = 消息列表[-1]

                    if 需要进入规划:
                        if len(消息列表) > 1:
                            logger.info(f"聊天流 [{self.chat_id}] 检测到队列积压 {len(消息列表)} 条消息，合并后统一处理")
                            合并内容 = "\n".join([f"[{m.get('sender_name', '未知')}] {m.get('message', '')}" for m in 消息列表])
                            用户消息 = {"role": "user", "content": 合并内容}
                        else:
                            logger.info(f"聊天流 [{self.chat_id}] 开始处理消息: {消息.get('message', '')[:50]}")
                            用户消息 = {"role": "user", "content": f"[{消息.get('sender_name', '未知')}] {消息.get('message', '')}"}

                        self.对话历史.append(用户消息)

                        _max = 回复模型配置.get("max_history", 20)
                        if len(self.对话历史) > _max:
                            self.对话历史 = self.对话历史[-_max:]

                        if 关闭规划模型:
                            if 回复模型配置.get("model"):
                                模型回复 = await self._调用AI模型()
                                if 模型回复 and not 模型回复.startswith("错误"):
                                    规划结果["回复内容"] = 模型回复
                                else:
                                    logger.error(f"模型调用失败: {模型回复}")
                            else:
                                logger.warning("已关闭规划模型且未配置回复模型，跳过AI回复")
                        elif 规划模型配置.get("model"):
                            规划结果 = await self._执行规划阶段(消息)
                        elif 回复模型配置.get("model"):
                            模型回复 = await self._调用AI模型()
                            if 模型回复 and not 模型回复.startswith("错误"):
                                规划结果["回复内容"] = 模型回复
                            else:
                                logger.error(f"模型调用失败: {模型回复}")
                    else:
                        最近消息摘要 = " | ".join([str(m.get("message", ""))[:40] for m in 消息列表])
                        logger.info(f"聊天流 [{self.chat_id}] 消息[{最近消息摘要}] 不回复，因为: {筛选原因 or '筛选模型判定无需回复'}")

                    if 规划结果.get("回复内容"):
                        待发送回复 = 规划结果.get("回复内容", "")
                    if 规划结果.get("跳过回复"):
                        跳过回复 = True

                    新消息列表 = []
                    while not self.消息队列.empty():
                        try:
                            新消息 = self.消息队列.get_nowait()
                            新消息列表.append(新消息)
                            本轮消息数 += 1
                        except asyncio.QueueEmpty:
                            break

                    if 新消息列表:
                        消息列表 = 新消息列表
                        消息 = 消息列表[-1]
                        continue

                    if not 规划结果.get("可继续合并", True):
                        break

                    剩余时间 = 截止时间 - asyncio.get_event_loop().time()
                    if 剩余时间 <= 0:
                        break

                    try:
                        新消息 = await asyncio.wait_for(self.消息队列.get(), timeout=剩余时间)
                        消息列表 = [新消息]
                        消息 = 新消息
                        本轮消息数 += 1
                        continue
                    except asyncio.TimeoutError:
                        break

                if 待发送回复 and not 跳过回复:
                    if not self.分割器已发送:
                        self.对话历史.append({"role": "assistant", "content": 待发送回复})
                        await self._发送回复(待发送回复)
                    else:
                        self.对话历史.append({"role": "assistant", "content": 待发送回复})
                        self.分割器已发送 = False
                
                self.处理状态 = "空闲"
                
            except asyncio.CancelledError:
                logger.info(f"聊天流 [{self.chat_id}] 处理循环被取消")
                break
            except Exception as 错误:
                logger.error(f"聊天流 [{self.chat_id}] 处理消息时出错: {错误}")
                self.处理状态 = "空闲"
            finally:
                for _ in range(本轮消息数):
                    self.消息队列.task_done()
    
    async def _执行规划阶段(self, 消息: dict):
        """
        调用规划模型分析消息，输出工具调用并执行
        """
        规划模型名 = 规划模型配置.get("model", "")
        规划system提示词 = 工具执行器.生成规划system提示词(规划模型配置.get("system_prompt", ""))
        最终结果 = {"回复内容": "", "跳过回复": False, "可继续合并": True}
        最大轮次 = 3

        if _插件管理器实例:
            钩子结果 = await _插件管理器实例.触发钩子(
                "on_pre_plan",
                聊天流=self,
                消息=消息,
                对话历史=self.对话历史,
            )
            if 钩子结果:
                注入历史 = 钩子结果.get("对话历史")
                if 注入历史 is not None:
                    self.对话历史 = 注入历史

        for 轮次 in range(1, 最大轮次 + 1):
            对话内容 = "\n".join([f"{m['role']}: {m['content']}" for m in self.对话历史])
            会话上下文 = f"\n\n[当前会话信息]\nchat_id: {self.chat_id}\nchat_type: {self.chat_type} (注意：chat_type 必须使用 'group' 或 'private'，不能使用中文)\n若需向当前会话发送消息，请使用此 chat_id 和 chat_type。\n当前规划轮次: {轮次}/{最大轮次}"

            if self.调试模式:
                logger.debug(f"[调试模式] 规划模型输入:\n=== System Prompt ===\n{规划system提示词}\n=== User Prompt ===\n{对话内容 + 会话上下文}\n=== End ===")

            规划输出 = await 调用模型(
                模型名=规划模型名,
                user提示词=对话内容 + 会话上下文,
                system提示词=规划system提示词,
                额外参数=规划模型配置.get("额外参数", {})
            )

            if not 规划输出 or 规划输出.startswith("错误"):
                logger.error(f"规划模型调用失败: {规划输出}")
                return 最终结果

            logger.info(f"规划模型输出: {规划输出[:200]}")

            工具调用列表 = 工具执行器.解析规划输出(规划输出)
            if not 工具调用列表:
                logger.warning("规划模型未输出有效工具调用")
                return 最终结果

            if _插件管理器实例:
                钩子结果 = await _插件管理器实例.触发钩子(
                    "on_post_plan",
                    聊天流=self,
                    工具调用列表=工具调用列表,
                )
                if 钩子结果:
                    修改后列表 = 钩子结果.get("工具调用列表")
                    if 修改后列表 is not None:
                        工具调用列表 = 修改后列表

            非回复工具 = []
            回复工具列表 = []
            多轮工具列表 = []
            不回复工具列表 = []

            for 工具调用 in 工具调用列表:
                工具名 = 工具调用.get("name", "")
                if 工具名 in ("回复工具", "回复"):
                    回复工具列表.append(工具调用)
                elif 工具名 in ("不回复工具", "不回复", "跳过回复"):
                    不回复工具列表.append(工具调用)
                elif 工具名 in ("多轮执行工具", "多轮执行", "继续规划", "继续执行"):
                    多轮工具列表.append(工具调用)
                else:
                    非回复工具.append(工具调用)

            工具执行摘要 = []
            for 工具调用 in 非回复工具:
                工具名 = 工具调用.get("name", "")
                结果 = await 工具执行器.执行工具调用(工具调用, self, 消息)
                logger.info(f"工具执行结果: {工具调用.get('name')} -> {结果.get('status')}")

                if _插件管理器实例:
                    结果 = await _插件管理器实例.触发修改钩子("on_post_tool", 结果)
                    工具名 = 结果.get("工具", 工具名) if isinstance(结果, dict) else 工具名

                摘要 = {
                    "工具": 工具名,
                    "状态": 结果.get("status", "unknown"),
                    "结果": 结果.get("message", "")
                }
                if 结果.get("data") is not None:
                    摘要["数据"] = 结果.get("data")
                工具执行摘要.append(摘要)

            if 工具执行摘要:
                注入内容 = (
                    "[系统通知] 以下工具已执行，供你生成准确回复：\n"
                    f"{json.dumps(工具执行摘要, ensure_ascii=False)}\n"
                    "请基于这些已执行结果直接回答用户，不要否认你已执行成功的操作。"
                )
                self.对话历史.append({"role": "system", "content": 注入内容})

            回复结果摘要 = []
            for 工具调用 in 回复工具列表:
                工具调用副本 = {
                    "name": 工具调用.get("name", "回复工具"),
                    "parameters": dict(工具调用.get("parameters", {}) or {})
                }
                工具调用副本["parameters"]["_仅生成不发送"] = True
                结果 = await 工具执行器.执行工具调用(工具调用副本, self, 消息)
                logger.info(f"工具执行结果: {工具调用.get('name')} -> {结果.get('status')}")
                回复结果摘要.append({
                    "状态": 结果.get("status", "unknown"),
                    "内容": 结果.get("message", "")
                })
                if 结果.get("status") == "success" and 结果.get("message"):
                    最终结果["回复内容"] = 结果.get("message", "")

            for 工具调用 in 不回复工具列表:
                结果 = await 工具执行器.执行工具调用(工具调用, self, 消息)
                logger.info(f"工具执行结果: {工具调用.get('name')} -> {结果.get('status')}")
                if 结果.get("status") == "success":
                    最终结果["跳过回复"] = True
                    最终结果["回复内容"] = ""

            多轮请求摘要 = []
            for 工具调用 in 多轮工具列表:
                结果 = await 工具执行器.执行工具调用(工具调用, self, 消息)
                logger.info(f"工具执行结果: {工具调用.get('name')} -> {结果.get('status')}")
                多轮请求摘要.append({
                    "参数": 工具调用.get("parameters", {}),
                    "结果": 结果.get("data", {}),
                })

            if 多轮请求摘要:
                if 轮次 >= 最大轮次:
                    logger.warning("多轮执行达到最大轮次，停止继续规划")
                    return 最终结果

                多轮上下文 = {
                    "轮次": 轮次,
                    "多轮请求": 多轮请求摘要,
                    "本轮非回复工具结果": 工具执行摘要,
                    "本轮回复结果": 回复结果摘要,
                }
                self.对话历史.append({
                    "role": "system",
                    "content": f"[多轮执行上下文] {json.dumps(多轮上下文, ensure_ascii=False)}\n请基于以上上下文继续下一轮规划。"
                })
                continue

            return 最终结果

        return 最终结果
    
    async def _调用AI模型(self) -> str:
        """
        调用AI模型，将当前对话历史发送给模型
        若消息分割器启用，则使用流式输出并在换行或句号处分段发送
        """
        模型名 = 回复模型配置.get("model", "")
        system提示词 = 回复模型配置.get("system_prompt", "你是一个乐于助人的AI助手。")
        额外参数 = dict(回复模型配置.get("额外参数", {}))
        分割器启用 = bool(回复逻辑配置.get("消息分割器", {}).get("启用", False))

        对话内容 = "\n".join([f"{m['role']}: {m['content']}" for m in self.对话历史])

        if _插件管理器实例:
            钩子结果 = await _插件管理器实例.触发钩子(
                "on_pre_reply",
                聊天流=self,
                system提示词=system提示词,
                user提示词=对话内容,
            )
            if 钩子结果:
                if 钩子结果.get("system提示词") is not None:
                    system提示词 = 钩子结果["system提示词"]
                if 钩子结果.get("user提示词") is not None:
                    对话内容 = 钩子结果["user提示词"]
        
        if self.调试模式:
            logger.debug(f"[调试模式] 回复模型输入:\n=== System Prompt ===\n{system提示词}\n=== User Prompt ===\n{对话内容}\n=== End ===")

        if 分割器启用:
            if 额外参数.get("stream") is not None:
                logger.warning("[消息分割器] 启用消息分割器后将忽略回复模型的stream参数")
                额外参数.pop("stream", None)
            try:
                完整回复 = await self._流式分割发送(模型名, 对话内容, system提示词, 额外参数)
            except Exception as e:
                logger.error(f"流式分割发送失败: {e}")
                return f"错误：{e}"
            if _插件管理器实例 and 完整回复:
                完整回复 = await _插件管理器实例.触发修改钩子("on_post_reply", 完整回复)
            return 完整回复

        模型回复 = await 调用模型(
            模型名=模型名,
            user提示词=对话内容,
            system提示词=system提示词,
            额外参数=额外参数
        ) or ""

        if _插件管理器实例 and 模型回复:
            模型回复 = await _插件管理器实例.触发修改钩子("on_post_reply", 模型回复)

        return 模型回复

    async def _流式分割发送(self, 模型名, user提示词, system提示词, 额外参数) -> str:
        """
        流式调用模型，在遇到换行或句号时分段发送消息
        流式输出到分隔符时立即发送并清空缓冲，不等待输出完毕
        分隔符本身不包含在发送内容中
        返回完整的模型回复内容（含分隔符）
        """
        import time
        累积内容 = ""
        待发送缓冲 = ""
        分隔符集合 = {"\n", "。"}
        分段计数 = 0
        起始时间 = time.time()
        上一段时间 = 起始时间

        try:
            async for 片段 in 调用模型流式(
                模型名=模型名,
                user提示词=user提示词,
                system提示词=system提示词,
                额外参数=额外参数,
            ):
                累积内容 += 片段
                待发送缓冲 += 片段

                发送点索引 = -1
                匹配分隔符长度 = 0
                for 分隔符 in 分隔符集合:
                    索引 = 待发送缓冲.rfind(分隔符)
                    if 索引 > 发送点索引:
                        发送点索引 = 索引
                        匹配分隔符长度 = len(分隔符)

                if 发送点索引 >= 0:
                    发送内容 = 待发送缓冲[:发送点索引]
                    待发送缓冲 = 待发送缓冲[发送点索引 + 匹配分隔符长度:]
                    if 发送内容:
                        分段计数 += 1
                        当前时间 = time.time()
                        logger.info(f"[消息分割器] 分段#{分段计数} 发送 ({当前时间-上一段时间:.1f}s): {发送内容[:50]}...")
                        上一段时间 = 当前时间
                        await self._发送回复(发送内容)
        except Exception as e:
            logger.error(f"流式分割发送失败: {e}")
            return f"错误：{e}"

        if 待发送缓冲.strip():
            await self._发送回复(待发送缓冲)

        self.分割器已发送 = True
        return 累积内容
    
    async def _发送回复(self, 回复内容: str):
        """
        将AI回复发送回对应的聊天会话
        """
        回复数据 = {
            "action": "send_message",
            "chat_type": self.chat_type,
            "chat_id": self.chat_id,
            "message": 回复内容,
        }

        if _插件管理器实例:
            回复数据 = await _插件管理器实例.触发过滤钩子("on_send_message", 回复数据)
            if 回复数据 is None:
                logger.info(f"[插件系统] 回复被 on_send_message 钩子拦截: {self.chat_id}")
                return
        
        import sys
        _main = sys.modules.get("main") or sys.modules.get("__main__")
        if _main and hasattr(_main, "发送回复到适配器"):
            成功 = await _main.发送回复到适配器(回复数据)
            if 成功:
                logger.info(f"AI回复已发送 [{self.chat_id}]: {回复内容[:100]}")
            else:
                logger.error(f"AI回复发送失败 [{self.chat_id}]")
        else:
            logger.warning(f"无法获取发送函数，AI回复仅记录日志 [{self.chat_id}]: {回复内容[:100]}")
    
    async def 添加消息(self, 消息数据: dict):
        """向聊天流添加消息"""
        await self.消息队列.put(消息数据)
        self.最后活跃时间 = asyncio.get_event_loop().time()
        logger.debug(f"聊天流 [{self.chat_id}] 收到新消息，当前队列长度: {self.消息队列.qsize()}")
    
    async def 停止(self):
        """停止聊天流"""
        self._运行中 = False
        if self._处理任务:
            self._处理任务.cancel()
            try:
                await self._处理任务
            except asyncio.CancelledError:
                pass
        logger.info(f"聊天流 [{self.chat_id}] 已停止")


class 聊天管理器:
    """
    聊天流管理器
    负责创建、分发、销毁聊天流
    """
    
    def __init__(self, 调试模式: bool = False):
        self.聊天流字典: dict[str, 聊天流] = {}
        self._锁 = asyncio.Lock()
        self.调试模式 = 调试模式
    
    async def 获取或创建聊天流(self, chat_id: str, chat_type: str, adapter: str) -> 聊天流:
        """
        获取现有聊天流，如果不存在则创建新的
        """
        async with self._锁:
            if chat_id not in self.聊天流字典:
                新聊天流 = 聊天流(chat_id, chat_type, adapter, 调试模式=self.调试模式)
                self.聊天流字典[chat_id] = 新聊天流
                await 新聊天流.启动处理循环()
                logger.info(f"创建新聊天流: {chat_id} (类型: {chat_type})")
            return self.聊天流字典[chat_id]
    
    async def 分发消息(self, 消息数据: dict):
        """
        将消息分发到对应的聊天流
        消息数据格式:
        {
            "adapter": "适配器名称",
            "chat_id": "聊天ID",
            "chat_type": "group/private",
            "sender_id": 发送者ID,
            "sender_name": "发送者名称",
            "message": "消息内容",
            "raw_data": {...}
        }
        """
        chat_id = 消息数据.get("chat_id")
        chat_type = 消息数据.get("chat_type", "private")
        adapter = 消息数据.get("adapter", "unknown")
        
        if not chat_id:
            logger.warning(f"收到无效消息，缺少 chat_id: {消息数据}")
            return
        
        if _插件管理器实例:
            消息数据 = await _插件管理器实例.触发过滤钩子("on_message_enqueue", 消息数据)
            if 消息数据 is None:
                logger.info(f"[插件系统] 消息被 on_message_enqueue 钩子拦截: chat_id={chat_id}")
                return
            chat_id = 消息数据.get("chat_id", chat_id)
            chat_type = 消息数据.get("chat_type", chat_type)
            adapter = 消息数据.get("adapter", adapter)
        
        聊天流 = await self.获取或创建聊天流(chat_id, chat_type, adapter)
        await 聊天流.添加消息(消息数据)
    
    async def 移除聊天流(self, chat_id: str):
        """移除并停止指定的聊天流"""
        async with self._锁:
            if chat_id in self.聊天流字典:
                await self.聊天流字典[chat_id].停止()
                del self.聊天流字典[chat_id]
                logger.info(f"已移除聊天流: {chat_id}")
    
    async def 获取所有聊天流(self) -> dict:
        """获取所有活跃聊天流的状态"""
        结果 = {}
        for chat_id, 流 in self.聊天流字典.items():
            结果[chat_id] = {
                "chat_type": 流.chat_type,
                "adapter": 流.adapter,
                "处理状态": 流.处理状态,
                "队列长度": 流.消息队列.qsize(),
                "对话历史长度": len(流.对话历史),
            }
        return 结果
    
    async def 停止所有(self):
        """停止所有聊天流"""
        logger.info(f"正在停止 {len(self.聊天流字典)} 个聊天流...")
        for chat_id in list(self.聊天流字典.keys()):
            await self.移除聊天流(chat_id)
        logger.info("所有聊天流已停止")
