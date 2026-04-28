# ==========================================
# 应用状态管理器 (应用状态.py)
# 功能：管理应用程序的全局状态，避免使用全局变量
# ==========================================
import asyncio
import json
from typing import Optional
from 模块.log模块 import logger


class 应用状态:
    """
    应用程序全局状态管理器（单例模式）
    封装所有全局状态，提供统一的访问接口
    """
    
    _实例: Optional['应用状态'] = None
    
    def __init__(self, 调试模式: bool = False):
        """
        初始化应用状态
        
        参数:
            调试模式: 是否启用调试模式
        """
        # 队列
        self.消息队列 = asyncio.Queue()
        self.待处理队列 = asyncio.Queue()
        
        # 管理器实例（延迟初始化，避免循环导入）
        self.聊天管理器 = None
        self.插件管理器 = None
        self.配置管理器 = None
        
        # 适配器状态
        self.适配器已连接 = False
        self.适配器连接地址 = None
        self.适配器WS连接 = None
        
        # API 等待池
        self.API等待池 = {}
        
        # 配置
        self.调试模式 = 调试模式
    
    @classmethod
    def 获取实例(cls, 调试模式: bool = False) -> '应用状态':
        """
        获取应用状态单例实例
        
        参数:
            调试模式: 是否启用调试模式（仅在首次创建时有效）
        
        返回:
            应用状态实例
        """
        if cls._实例 is None:
            cls._实例 = cls(调试模式=调试模式)
        return cls._实例
    
    def 设置聊天管理器(self, 管理器):
        """设置聊天管理器实例"""
        self.聊天管理器 = 管理器
    
    def 设置插件管理器(self, 管理器):
        """设置插件管理器实例"""
        self.插件管理器 = 管理器
    
    def 设置配置管理器(self, 管理器):
        """设置配置管理器实例"""
        self.配置管理器 = 管理器
    
    async def 发送回复到适配器(self, 回复数据: dict) -> bool:
        """
        将AI回复通过 WebSocket 发送回适配器
        
        参数:
            回复数据: 要发送的回复数据
        
        返回:
            bool: 发送是否成功
        """
        if self.适配器WS连接:
            try:
                await self.适配器WS连接.send(json.dumps(回复数据, ensure_ascii=False))
                return True
            except Exception as e:
                logger.error(f"发送回复到适配器失败: {e}")
        else:
            logger.error("适配器未连接，无法发送回复")
        return False
    
    async def 调用适配器API(self, action: str, params: dict, timeout: int = 15) -> dict:
        """
        通过适配器调用Napcat API，等待响应
        
        参数:
            action: API 动作名称
            params: API 参数
            timeout: 超时时间（秒）
        
        返回:
            dict: API 响应结果
        """
        import uuid
        请求ID = str(uuid.uuid4())
        事件 = asyncio.Event()
        self.API等待池[请求ID] = {"事件": 事件, "响应": None}
        
        请求数据 = {
            "action": "call_api",
            "echo": 请求ID,
            "api_action": action,
            "api_params": params
        }
        
        成功 = await self.发送回复到适配器(请求数据)
        if not 成功:
            del self.API等待池[请求ID]
            return {"status": "error", "message": "适配器未连接"}
        
        try:
            await asyncio.wait_for(事件.wait(), timeout=timeout)
            结果 = self.API等待池[请求ID]["响应"]
            return 结果
        except asyncio.TimeoutError:
            logger.error(f"API调用超时: {action}")
            return {"status": "error", "message": "超时"}
        finally:
            if 请求ID in self.API等待池:
                del self.API等待池[请求ID]
    
    async def 处理API响应(self, 响应数据: dict):
        """
        处理适配器返回的API响应
        
        参数:
            响应数据: API 响应数据
        """
        echo = 响应数据.get("echo")
        if echo and echo in self.API等待池:
            self.API等待池[echo]["响应"] = 响应数据
            self.API等待池[echo]["事件"].set()
        else:
            logger.warning(f"收到未知API响应: {echo}")
    
    def 设置适配器连接(self, websocket, 地址):
        """
        设置适配器连接状态
        
        参数:
            websocket: WebSocket 连接对象
            地址: 连接地址
        """
        self.适配器连接地址 = 地址
        self.适配器WS连接 = websocket
        self.适配器已连接 = True
        logger.info(f"适配器已连接: {地址}")
    
    def 断开适配器连接(self):
        """断开适配器连接"""
        if self.适配器连接地址:
            logger.info(f"适配器已断开: {self.适配器连接地址}")
        self.适配器已连接 = False
        self.适配器WS连接 = None
        self.适配器连接地址 = None
    
    def 获取状态摘要(self) -> dict:
        """
        获取应用状态摘要
        
        返回:
            dict: 状态摘要信息
        """
        return {
            "调试模式": self.调试模式,
            "适配器已连接": self.适配器已连接,
            "适配器地址": str(self.适配器连接地址) if self.适配器连接地址 else None,
            "消息队列长度": self.消息队列.qsize(),
            "待处理队列长度": self.待处理队列.qsize(),
            "API等待池大小": len(self.API等待池),
        }


# 便捷函数：获取全局应用状态实例
def 获取应用状态(调试模式: bool = False) -> 应用状态:
    """
    获取全局应用状态实例
    
    参数:
        调试模式: 是否启用调试模式（仅在首次创建时有效）
    
    返回:
        应用状态实例
    """
    return 应用状态.获取实例(调试模式=调试模式)


if __name__ == "__main__":
    """测试应用状态管理器"""
    状态 = 获取应用状态(调试模式=True)
    print("应用状态摘要:")
    print(状态.获取状态摘要())
