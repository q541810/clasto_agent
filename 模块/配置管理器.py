# ==========================================
# 配置管理器 (配置管理器.py)
# 功能：统一管理所有配置文件的读取和访问
# ==========================================
import os
import shutil
import toml
from 模块.log模块 import logger

class 配置管理器:
    """统一的配置管理类，负责读取和缓存所有配置"""
    
    def __init__(self):
        # 项目根目录
        self.项目根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.配置文件目录 = os.path.join(self.项目根目录, "配置文件")
        self.模板目录 = os.path.join(self.项目根目录, "配置文件模板")
        
        # 配置缓存
        self._api配置 = None
        self._模型配置 = None
        self._运行时配置 = None
        
        # 初始化配置
        self._初始化所有配置()
    
    def _初始化所有配置(self):
        """初始化所有配置文件"""
        # 确保配置目录存在
        if not os.path.exists(self.配置文件目录):
            os.makedirs(self.配置文件目录)
            logger.info(f"创建配置目录: {self.配置文件目录}")
        
        # 初始化各个配置文件
        self._初始化配置文件("api_config.toml")
        self._初始化配置文件("model_config.toml")
        self._初始化配置文件("runtime_config.toml")
    
    def _初始化配置文件(self, 文件名: str):
        """初始化单个配置文件"""
        配置文件路径 = os.path.join(self.配置文件目录, 文件名)
        模板路径 = os.path.join(self.模板目录, 文件名)
        
        if not os.path.exists(配置文件路径):
            if os.path.exists(模板路径):
                try:
                    shutil.copy(模板路径, 配置文件路径)
                    logger.warning(f"配置文件不存在，已从模板创建: {配置文件路径}")
                    logger.warning(f"请填写 {文件名} 后重新运行程序")
                except Exception as e:
                    logger.error(f"复制配置模板失败 ({文件名}): {e}")
            else:
                logger.error(f"配置文件和模板都不存在: {文件名}")
    
    def _读取toml文件(self, 文件名: str) -> dict:
        """读取TOML配置文件"""
        文件路径 = os.path.join(self.配置文件目录, 文件名)
        
        if not os.path.exists(文件路径):
            logger.warning(f"配置文件不存在: {文件路径}")
            return {}
        
        try:
            with open(文件路径, "r", encoding="utf-8") as f:
                配置数据 = toml.load(f)
                logger.info(f"成功加载配置: {文件名}")
                return 配置数据
        except toml.TomlDecodeError as e:
            logger.error(f"配置文件格式错误 ({文件名}): {e}")
            return {}
        except Exception as e:
            logger.error(f"读取配置文件失败 ({文件名}): {e}")
            return {}
    
    def 获取api配置(self) -> dict:
        """获取API配置（缓存）"""
        if self._api配置 is None:
            self._api配置 = self._读取toml文件("api_config.toml")
        return self._api配置
    
    def 获取模型配置(self) -> dict:
        """获取模型配置（缓存）"""
        if self._模型配置 is None:
            self._模型配置 = self._读取toml文件("model_config.toml")
        return self._模型配置
    
    def 获取运行时配置(self) -> dict:
        """获取运行时配置（缓存）"""
        if self._运行时配置 is None:
            self._运行时配置 = self._读取toml文件("runtime_config.toml")
        return self._运行时配置
    
    def 获取回复模型配置(self) -> dict:
        """获取回复模型配置"""
        模型配置 = self.获取模型配置()
        回复模型 = 模型配置.get("回复模型", {})
        
        return {
            "model": 回复模型.get("model", ""),
            "system_prompt": 回复模型.get("system_prompt", ""),
            "max_history": 回复模型.get("max_history", 20),
            "额外参数": 回复模型.get("额外参数", {}) if isinstance(回复模型.get("额外参数", {}), dict) else {}
        }
    
    def 获取规划模型配置(self) -> dict:
        """获取规划模型配置"""
        模型配置 = self.获取模型配置()
        规划模型 = 模型配置.get("规划模型", {})
        
        return {
            "model": 规划模型.get("model", ""),
            "system_prompt": 规划模型.get("system_prompt", ""),
            "额外参数": 规划模型.get("额外参数", {}) if isinstance(规划模型.get("额外参数", {}), dict) else {}
        }
    
    def 获取筛选模型配置(self) -> dict:
        """获取筛选模型配置"""
        模型配置 = self.获取模型配置()
        筛选模型 = 模型配置.get("筛选模型", {})
        
        return {
            "model": 筛选模型.get("model", ""),
            "system_prompt": 筛选模型.get("system_prompt", ""),
            "额外参数": 筛选模型.get("额外参数", {}) if isinstance(筛选模型.get("额外参数", {}), dict) else {}
        }
    
    def 获取回复逻辑配置(self) -> dict:
        """获取回复逻辑配置"""
        运行时配置 = self.获取运行时配置()
        
        # 默认配置
        默认配置 = {
            "bot的名字": "bot",
            "模型调用自动重试次数": 1,
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
            },
            "消息分割器": {
                "启用": False,
            }
        }
        
        # 合并用户配置
        配置 = 默认配置.copy()
        配置["bot的名字"] = str(运行时配置.get("bot的名字", 默认配置["bot的名字"]))
        配置["模型调用自动重试次数"] = int(运行时配置.get("模型调用自动重试次数", 默认配置["模型调用自动重试次数"]))
        
        # 群聊配置
        群聊配置 = 运行时配置.get("群聊回复逻辑", {})
        配置["群聊"]["mode"] = 群聊配置.get("mode", 默认配置["群聊"]["mode"])
        配置["群聊"]["关闭规划模型"] = bool(群聊配置.get("关闭规划模型", 默认配置["群聊"]["关闭规划模型"]))
        
        # 私聊配置
        私聊配置 = 运行时配置.get("私聊回复逻辑", {})
        配置["私聊"]["mode"] = 私聊配置.get("mode", 默认配置["私聊"]["mode"])
        配置["私聊"]["关闭规划模型"] = bool(私聊配置.get("关闭规划模型", 默认配置["私聊"]["关闭规划模型"]))
        
        # 群聊回复优化配置（兼容旧版配置）
        群聊回复优化 = 运行时配置.get("群聊回复优化", {})
        旧_原因最大字数 = 群聊配置.get("原因最大字数", 默认配置["群聊回复优化"]["原因最大字数"])
        旧_at必回复 = 群聊配置.get("at必回复", 默认配置["群聊回复优化"]["at必回复"])
        旧_提及关键词 = 群聊配置.get("提及关键词", 默认配置["群聊回复优化"]["提及关键词"])
        
        配置["群聊回复优化"]["原因最大字数"] = int(群聊回复优化.get("原因最大字数", 旧_原因最大字数))
        配置["群聊回复优化"]["上下文条数"] = int(群聊回复优化.get("上下文条数", 默认配置["群聊回复优化"]["上下文条数"]))
        配置["群聊回复优化"]["at必回复"] = bool(群聊回复优化.get("at必回复", 旧_at必回复))
        配置["群聊回复优化"]["提及关键词"] = 群聊回复优化.get("提及关键词", 旧_提及关键词)
        
        # 消息分割器配置
        消息分割器 = 运行时配置.get("消息分割器", {})
        配置["消息分割器"]["启用"] = bool(消息分割器.get("启用", 默认配置["消息分割器"]["启用"]))
        
        return 配置
    
    def 获取模型列表配置(self) -> list:
        """
        获取模型列表配置（兼容旧版格式）
        返回格式：[[模型名, 厂商, 模型id, url, api_key], ...     """
        api配置 = self.获取api配置()
        模型配置列表 = api配置.get("模型配置", {})
        厂商配置 = api配置.get("现有模型厂商", {})
        
        结果 = []
        for 模型名, 模型信息 in 模型配置列表.items():
            厂商名 = 模型信息.get("厂商", "")
            模型id = 模型信息.get("模型id", "")
            厂商信息 = 厂商配置.get(厂商名, {})
            url = 厂商信息.get("url", "")
            api_key = 厂商信息.get("api_key", "")
            
            结果.append([模型名, 厂商名, 模型id, url, api_key])
        
        return 结果
    
    def 重新加载配置(self):
        """重新加载所有配置（清除缓存）"""
        self._api配置 = None
        self._模型配置 = None
        self._运行时配置 = None
        logger.info("配置已重新加载")


# 全局配置管理器实例
_配置管理器实例 = None

def 获取配置管理器() -> 配置管理器:
    """获取全局配置管理器实例（单例模式）"""
    global _配置管理器实例
    if _配置管理器实例 is None:
        _配置管理器实例 = 配置管理器()
    return _配置管理器实例


# 为了兼容旧代码，保留旧的导出变量
配置管理器实例 = 获取配置管理器()
配置内容 = 配置管理器实例.获取api配置()
模型配置 = 配置管理器实例.获取模型列表配置()


if __name__ == "__main__":
    """测试配置管理器"""
    管理器 = 获取配置管理器()
    
    print("=== API配置 ===")
    print(管理器.获取api配置())
    print()
    
    print("=== 回复模型配置 ===")
    print(管理器.获取回复模型配置())
    print()
    
    print("=== 规划模型配置 ===")
    print(管理器.获取规划模型配置())
    print()
    
    print("=== 回复逻辑配置 ===")
    print(管理器.获取回复逻辑配置())
    print()
    
    print("=== 模型列表 ===")
    for 模型 in 管理器.获取模型列表配置():
        print(模型)
