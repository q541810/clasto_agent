# ==========================================
# 插件管理器 (插件管理器.py)
# 功能：扫描、加载、管理插件，注册钩子与调度
# ==========================================
import os
import sys
import importlib
import asyncio
import toml
from 模块.log模块 import logger

项目根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
插件目录 = os.path.join(项目根目录, "插件")
插件配置目录 = os.path.join(项目根目录, "插件配置")


class 插件上下文:
    """
    每个插件获得的上下文对象，提供注册工具、钩子、调用API等能力
    """
    def __init__(self, 插件信息: dict, 管理器):
        self._插件信息 = 插件信息
        self._管理器 = 管理器
        self._配置 = 插件信息.get("配置", {})

    @property
    def 名称(self) -> str:
        return self._插件信息.get("name", "未知插件")

    @property
    def 版本(self) -> str:
        return self._插件信息.get("version", "0.0.0")

    @property
    def 插件目录(self) -> str:
        return self._插件信息.get("目录", "")

    def 获取配置(self, 键: str = None, 默认值=None):
        if 键 is None:
            return dict(self._配置)
        return self._配置.get(键, 默认值)

    def 注册工具(self, 名称, 工具函数, 别名=None, 参数说明=None, 说明="", 是否回复工具=False):
        from 模块 import 工具执行器
        工具执行器.工具注册表.注册(
            名称=名称,
            工具函数=工具函数,
            别名=别名,
            参数说明=参数说明 or {},
            说明=说明,
            是否回复工具=是否回复工具,
        )
        self._管理器._记录插件工具(self.名称, 名称)
        logger.info(f"[插件系统] 插件 [{self.名称}] 注册了工具: {名称}")

    def 注册钩子(self, hook名: str, 回调):
        self._管理器._注册钩子(hook名, 回调, self.名称, self._插件信息.get("priority", 100))
        logger.info(f"[插件系统] 插件 [{self.名称}] 注册了钩子: {hook名}")

    async def 调用适配器API(self, action: str, params: dict, timeout: int = 15) -> dict:
        _main = sys.modules.get("main") or sys.modules.get("__main__")
        if _main and hasattr(_main, "调用适配器API"):
            return await _main.调用适配器API(action, params, timeout)
        logger.warning(f"[插件系统] 无法调用适配器API: {action}")
        return {"status": "error", "message": "适配器API不可用"}

    def 获取聊天流(self, chat_id: str):
        _main = sys.modules.get("main") or sys.modules.get("__main__")
        if _main and hasattr(_main, "管理器"):
            return _main.管理器.聊天流字典.get(chat_id)
        return None

    async def 发送消息(self, chat_id: str, chat_type: str, message: str) -> bool:
        _main = sys.modules.get("main") or sys.modules.get("__main__")
        if _main and hasattr(_main, "发送回复到适配器"):
            回复数据 = {
                "action": "send_message",
                "chat_type": chat_type,
                "chat_id": chat_id,
                "message": message,
            }
            return await _main.发送回复到适配器(回复数据)
        logger.warning(f"[插件系统] 无法发送消息: {chat_id}")
        return False


class 插件管理器:
    """
    管理所有插件的加载、卸载、钩子调度
    """

    def __init__(self):
        self._已加载插件: dict[str, dict] = {}
        self._钩子注册表: dict[str, list] = {}
        self._插件工具映射: dict[str, list] = {}

    def _注册钩子(self, hook名: str, 回调, 插件名: str, 优先级: int = 100):
        if hook名 not in self._钩子注册表:
            self._钩子注册表[hook名] = []
        self._钩子注册表[hook名].append({
            "回调": 回调,
            "插件名": 插件名,
            "优先级": 优先级,
        })
        self._钩子注册表[hook名].sort(key=lambda x: x["优先级"])

    def _记录插件工具(self, 插件名: str, 工具名: str):
        if 插件名 not in self._插件工具映射:
            self._插件工具映射[插件名] = []
        self._插件工具映射[插件名].append(工具名)

    async def 触发钩子(self, hook名: str, **kwargs):
        """
        触发指定钩子，按优先级串行执行
        钩子类型：
          - 过滤型（on_message_receive, on_send_message）：任一回调返回None则拦截
          - 修改型（on_pre_plan, on_post_plan, on_post_tool, on_pre_reply, on_post_reply）：逐步传递修改后的数据
          - 通知型（on_load, on_unload, on_message_enqueue, on_post_tool）：仅通知，不修改数据
        """
        钩子列表 = self._钩子注册表.get(hook名, [])
        if not 钩子列表:
            return kwargs

        过滤型钩子 = {"on_message_receive", "on_send_message"}
        修改型钩子 = {"on_post_plan", "on_post_reply"}

        for 钩子 in 钩子列表:
            try:
                结果 = await 钩子["回调"](**kwargs)
                if hook名 in 过滤型钩子:
                    if 结果 is None:
                        logger.info(f"[插件系统] 钩子 [{hook名}] 被插件 [{钩子['插件名']}] 拦截")
                        return None
                elif hook名 in 修改型钩子:
                    if 结果 is not None and isinstance(结果, dict):
                        kwargs.update(结果)
            except Exception as e:
                logger.error(f"[插件系统] 钩子 [{hook名}] 执行失败，插件 [{钩子['插件名']}]: {e}")

        return kwargs

    async def 触发过滤钩子(self, hook名: str, 数据: dict) -> dict | None:
        """
        触发过滤型钩子，返回None表示拦截
        """
        钩子列表 = self._钩子注册表.get(hook名, [])
        for 钩子 in 钩子列表:
            try:
                结果 = await 钩子["回调"](数据)
                if 结果 is None:
                    logger.info(f"[插件系统] 数据被插件 [{钩子['插件名']}] 在钩子 [{hook名}] 中拦截")
                    return None
                if isinstance(结果, dict):
                    数据 = 结果
            except Exception as e:
                logger.error(f"[插件系统] 过滤钩子 [{hook名}] 执行失败，插件 [{钩子['插件名']}]: {e}")
        return 数据

    async def 触发修改钩子(self, hook名: str, 数据):
        """
        触发修改型钩子，前一个的输出作为下一个的输入
        """
        钩子列表 = self._钩子注册表.get(hook名, [])
        for 钩子 in 钩子列表:
            try:
                结果 = await 钩子["回调"](数据)
                if 结果 is not None:
                    数据 = 结果
            except Exception as e:
                logger.error(f"[插件系统] 修改钩子 [{hook名}] 执行失败，插件 [{钩子['插件名']}]: {e}")
        return 数据

    async def 触发通知钩子(self, hook名: str, **kwargs):
        """
        触发通知型钩子，仅通知所有插件，不关心返回值
        """
        钩子列表 = self._钩子注册表.get(hook名, [])
        for 钩子 in 钩子列表:
            try:
                await 钩子["回调"](**kwargs)
            except Exception as e:
                logger.error(f"[插件系统] 通知钩子 [{hook名}] 执行失败，插件 [{钩子['插件名']}]: {e}")

    async def 扫描并加载所有插件(self):
        """
        扫描插件目录，加载所有有效插件
        """
        if not os.path.exists(插件目录):
            os.makedirs(插件目录, exist_ok=True)
            logger.info(f"[插件系统] 已创建插件目录: {插件目录}")
            return

        if not os.path.exists(插件配置目录):
            os.makedirs(插件配置目录, exist_ok=True)

        try:
            子目录列表 = [
                d for d in os.listdir(插件目录)
                if os.path.isdir(os.path.join(插件目录, d))
                and not d.startswith(".")
                and not d.startswith("__")
            ]
        except Exception as e:
            logger.error(f"[插件系统] 扫描插件目录失败: {e}")
            return

        if not 子目录列表:
            logger.info("[插件系统] 未发现任何插件")
            return

        logger.info(f"[插件系统] 发现 {len(子目录列表)} 个插件目录: {子目录列表}")

        for 目录名 in 子目录列表:
            try:
                await self._加载插件(目录名)
            except Exception as e:
                logger.error(f"[插件系统] 加载插件 [{目录名}] 失败: {e}")

        logger.info(f"[插件系统] 插件加载完成，共加载 {len(self._已加载插件)} 个插件")

    async def _加载插件(self, 目录名: str):
        """
        加载单个插件
        """
        插件路径 = os.path.join(插件目录, 目录名)
        清单路径 = os.path.join(插件路径, "plugin.toml")
        入口路径 = os.path.join(插件路径, "main.py")

        if not os.path.exists(清单路径):
            logger.warning(f"[插件系统] 插件 [{目录名}] 缺少 plugin.toml，跳过")
            return

        try:
            with open(清单路径, "r", encoding="utf-8") as f:
                插件配置 = toml.load(f)
        except Exception as e:
            logger.error(f"[插件系统] 插件 [{目录名}] 读取 plugin.toml 失败: {e}")
            return

        插件元信息 = 插件配置.get("plugin", {})
        插件名 = 插件元信息.get("name", 目录名)
        插件版本 = 插件元信息.get("version", "0.0.0")
        插件描述 = 插件元信息.get("description", "")
        插件优先级 = int(插件元信息.get("priority", 100))

        if 插件名 in self._已加载插件:
            logger.warning(f"[插件系统] 插件 [{插件名}] 已加载，跳过重复加载")
            return

        默认配置 = 插件配置.get("config", {})
        用户配置 = self._加载用户配置(插件名)
        合并配置 = {**默认配置, **用户配置}

        if not os.path.exists(入口路径):
            logger.warning(f"[插件系统] 插件 [{插件名}] 缺少 main.py，跳过")
            return

        插件信息 = {
            "name": 插件名,
            "version": 插件版本,
            "description": 插件描述,
            "priority": 插件优先级,
            "目录": 插件路径,
            "配置": 合并配置,
        }

        上下文 = 插件上下文(插件信息, self)

        原始sys路径 = sys.path.copy()
        try:
            if 插件路径 not in sys.path:
                sys.path.insert(0, 插件路径)

            module_name = f"插件.{目录名}.main"
            if module_name in sys.modules:
                del sys.modules[module_name]

            try:
                插件模块 = importlib.import_module(module_name)
            except ImportError:
                spec = importlib.util.spec_from_file_location(module_name, 入口路径)
                if spec and spec.loader:
                    插件模块 = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = 插件模块
                    spec.loader.exec_module(插件模块)
                else:
                    raise ImportError(f"无法加载插件模块: {module_name}")

            入口函数 = getattr(插件模块, "入口", None) or getattr(插件模块, "setup", None)
            if 入口函数 is None:
                logger.warning(f"[插件系统] 插件 [{插件名}] main.py 中未找到入口函数 入口 或 setup，跳过")
                return

            if asyncio.iscoroutinefunction(入口函数):
                await 入口函数(上下文)
            else:
                入口函数(上下文)

            self._已加载插件[插件名] = 插件信息
            logger.info(f"[插件系统] 插件 [{插件名}] v{插件版本} 加载成功")

        except Exception as e:
            logger.error(f"[插件系统] 插件 [{插件名}] 加载异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            sys.path = 原始sys路径

    def _加载用户配置(self, 插件名: str) -> dict:
        """
        加载用户覆写的插件配置
        """
        用户配置路径 = os.path.join(插件配置目录, f"{插件名}.toml")
        if not os.path.exists(用户配置路径):
            return {}

        try:
            with open(用户配置路径, "r", encoding="utf-8") as f:
                return toml.load(f)
        except Exception as e:
            logger.warning(f"[插件系统] 读取插件 [{插件名}] 用户配置失败: {e}")
            return {}

    async def 卸载所有插件(self):
        """
        触发所有插件的 on_unload 钩子
        """
        logger.info("[插件系统] 正在卸载所有插件...")
        await self.触发通知钩子("on_unload")
        self._已加载插件.clear()
        logger.info("[插件系统] 所有插件已卸载")

    def 获取已加载插件列表(self) -> list[dict]:
        """
        返回所有已加载插件的信息列表
        """
        return [
            {
                "name": info.get("name", "未知"),
                "version": info.get("version", "0.0.0"),
                "description": info.get("description", ""),
            }
            for info in self._已加载插件.values()
        ]

    def 获取钩子统计(self) -> dict:
        """
        返回钩子注册统计
        """
        return {
            hook名: len(钩子列表)
            for hook名, 钩子列表 in self._钩子注册表.items()
        }