# ==========================================
# 配置验证器 (配置验证器.py)
# 功能：验证配置文件的完整性和正确性
# ==========================================
from typing import Dict, List, Tuple
from 模块.log模块 import logger


class 配置验证结果:
    """配置验证结果"""
    
    def __init__(self):
        self.错误列表: List[str] = []
        self.警告列表: List[str] = []
        self.信息列表: List[str] = []
    
    def 添加错误(self, 消息: str):
        self.错误列表.append(f"[错误] {消息}")
    
    def 添加警告(self, 消息: str):
        self.警告列表.append(f"[警告] {消息}")
    
    def 添加信息(self, 消息: str):
        self.信息列表.append(f"[信息] {消息}")
    
    def 是否有错误(self) -> bool:
        return len(self.错误列表) > 0
    
    def 是否有警告(self) -> bool:
        return len(self.警告列表) > 0
    
    def 获取所有消息(self) -> List[str]:
        return self.错误列表 + self.警告列表 + self.信息列表
    
    def 打印结果(self):
        """打印验证结果"""
        if self.错误列表:
            logger.error("配置验证发现错误:")
            for 错误 in self.错误列表:
                logger.error(f"  {错误}")
        
        if self.警告列表:
            logger.warning("配置验证发现警告:")
            for 警告 in self.警告列表:
                logger.warning(f"  {警告}")
        
        if self.信息列表:
            for 信息 in self.信息列表:
                logger.info(f"  {信息}")
        
        if not self.错误列表 and not self.警告列表:
            logger.info("[OK] 配置验证通过")


class 配置验证器:
    """配置验证器，验证所有配置文件的完整性"""
    
    @staticmethod
    def 验证API配置(api配置: dict) -> 配置验证结果:
        """验证 API 配置"""
        结果 = 配置验证结果()
        
        # 检查现有模型厂商
        厂商配置 = api配置.get("现有模型厂商", {})
        if not 厂商配置:
            结果.添加错误("未配置任何模型厂商 (现有模型厂商)")
            return 结果
        
        # 验证每个厂商的配置
        for 厂商名, 厂商信息 in 厂商配置.items():
            if not isinstance(厂商信息, dict):
                结果.添加错误(f"厂商 '{厂商名}' 配置格式错误")
                continue
            
            url = 厂商信息.get("url", "").strip()
            api_key = 厂商信息.get("api_key", "").strip()
            
            if not url:
                结果.添加错误(f"厂商 '{厂商名}' 缺少 URL")
            elif not url.startswith("http"):
                结果.添加警告(f"厂商 '{厂商名}' 的 URL 格式可能不正确: {url}")
            
            if not api_key:
                结果.添加警告(f"厂商 '{厂商名}' 的 API Key 为空")
            elif api_key in ["换成你自己的api_key", "your_api_key_here"]:
                结果.添加错误(f"厂商 '{厂商名}' 的 API Key 未修改，仍为模板默认值")
        
        # 检查模型配置
        模型配置 = api配置.get("模型配置", {})
        if not 模型配置:
            结果.添加错误("未配置任何模型 (模型配置)")
            return 结果
        
        # 验证每个模型的配置
        for 模型名, 模型信息 in 模型配置.items():
            if not isinstance(模型信息, dict):
                结果.添加错误(f"模型 '{模型名}' 配置格式错误")
                continue
            
            厂商 = 模型信息.get("厂商", "").strip()
            模型id = 模型信息.get("模型id", "").strip()
            
            if not 厂商:
                结果.添加错误(f"模型 '{模型名}' 缺少厂商配置")
            elif 厂商 not in 厂商配置:
                结果.添加错误(f"模型 '{模型名}' 引用的厂商 '{厂商}' 不存在")
            
            if not 模型id:
                结果.添加错误(f"模型 '{模型名}' 缺少模型ID")
        
        结果.添加信息(f"已配置 {len(厂商配置)} 个厂商，{len(模型配置)} 个模型")
        return 结果
    
    @staticmethod
    def 验证模型配置(模型配置: dict, api配置: dict) -> 配置验证结果:
        """验证模型配置"""
        结果 = 配置验证结果()
        
        可用模型列表 = list(api配置.get("模型配置", {}).keys())
        
        # 验证回复模型
        回复模型 = 模型配置.get("回复模型", {})
        if not isinstance(回复模型, dict):
            结果.添加错误("回复模型配置格式错误")
        else:
            模型名 = 回复模型.get("model", "").strip()
            if not 模型名:
                结果.添加错误("回复模型未配置 (model 字段为空)")
            elif 模型名 not in 可用模型列表:
                结果.添加错误(f"回复模型 '{模型名}' 在 api_config.toml 中不存在")
            
            system_prompt = 回复模型.get("system_prompt", "").strip()
            if not system_prompt:
                结果.添加警告("回复模型的 system_prompt 为空")
            
            max_history = 回复模型.get("max_history")
            if max_history is not None:
                try:
                    max_history = int(max_history)
                    if max_history < 1:
                        结果.添加警告(f"回复模型的 max_history ({max_history}) 应该大于 0")
                    elif max_history > 100:
                        结果.添加警告(f"回复模型的 max_history ({max_history}) 过大，可能影响性能")
                except (ValueError, TypeError):
                    结果.添加错误(f"回复模型的 max_history 格式错误: {max_history}")
        
        # 验证规划模型（可选）
        规划模型 = 模型配置.get("规划模型", {})
        if isinstance(规划模型, dict):
            模型名 = 规划模型.get("model", "").strip()
            if 模型名:
                if 模型名 not in 可用模型列表:
                    结果.添加错误(f"规划模型 '{模型名}' 在 api_config.toml 中不存在")
                else:
                    结果.添加信息(f"已配置规划模型: {模型名}")
            else:
                结果.添加信息("未配置规划模型，将跳过工具调用阶段")
        
        # 验证筛选模型（可选）
        筛选模型 = 模型配置.get("筛选模型", {})
        if isinstance(筛选模型, dict):
            模型名 = 筛选模型.get("model", "").strip()
            if 模型名:
                if 模型名 not in 可用模型列表:
                    结果.添加错误(f"筛选模型 '{模型名}' 在 api_config.toml 中不存在")
                else:
                    结果.添加信息(f"已配置筛选模型: {模型名}")
            else:
                结果.添加信息("未配置筛选模型，群聊回复优化将默认放行")
        
        return 结果
    
    @staticmethod
    def 验证运行时配置(运行时配置: dict) -> 配置验证结果:
        """验证运行时配置"""
        结果 = 配置验证结果()
        
        # 验证 bot 名字
        bot名字 = 运行时配置.get("bot的名字", "").strip()
        if not bot名字:
            结果.添加警告("bot的名字未配置，将使用默认值 'bot'")
        
        # 验证重试次数
        重试次数 = 运行时配置.get("模型调用自动重试次数")
        if 重试次数 is not None:
            try:
                重试次数 = int(重试次数)
                if 重试次数 < 0:
                    结果.添加警告(f"模型调用自动重试次数 ({重试次数}) 不应为负数")
                elif 重试次数 > 5:
                    结果.添加警告(f"模型调用自动重试次数 ({重试次数}) 过大，可能影响响应速度")
            except (ValueError, TypeError):
                结果.添加错误(f"模型调用自动重试次数格式错误: {重试次数}")
        
        # 验证群聊回复逻辑
        群聊配置 = 运行时配置.get("群聊回复逻辑", {})
        if isinstance(群聊配置, dict):
            mode = 群聊配置.get("mode", "").strip()
            if mode and mode not in ["群聊回复优化", "直接规划"]:
                结果.添加警告(f"群聊回复逻辑的 mode '{mode}' 不是有效值 (应为 '群聊回复优化' 或 '直接规划')")
        
        # 验证私聊回复逻辑
        私聊配置 = 运行时配置.get("私聊回复逻辑", {})
        if isinstance(私聊配置, dict):
            mode = 私聊配置.get("mode", "").strip()
            if mode and mode not in ["群聊回复优化", "直接规划"]:
                结果.添加警告(f"私聊回复逻辑的 mode '{mode}' 不是有效值 (应为 '群聊回复优化' 或 '直接规划')")
        
        # 验证群聊回复优化配置
        群聊回复优化 = 运行时配置.get("群聊回复优化", {})
        if isinstance(群聊回复优化, dict):
            上下文条数 = 群聊回复优化.get("上下文条数")
            if 上下文条数 is not None:
                try:
                    上下文条数 = int(上下文条数)
                    if 上下文条数 < 0:
                        结果.添加警告(f"群聊回复优化的上下文条数 ({上下文条数}) 不应为负数")
                    elif 上下文条数 > 20:
                        结果.添加警告(f"群聊回复优化的上下文条数 ({上下文条数}) 过大，可能影响性能")
                except (ValueError, TypeError):
                    结果.添加错误(f"群聊回复优化的上下文条数格式错误: {上下文条数}")
        
        return 结果
    
    @classmethod
    def 验证所有配置(cls, 配置管理器) -> 配置验证结果:
        """验证所有配置文件"""
        总结果 = 配置验证结果()
        
        # 验证 API 配置
        api配置 = 配置管理器.获取api配置()
        if not api配置:
            总结果.添加错误("无法读取 api_config.toml")
            return 总结果
        
        api结果 = cls.验证API配置(api配置)
        总结果.错误列表.extend(api结果.错误列表)
        总结果.警告列表.extend(api结果.警告列表)
        总结果.信息列表.extend(api结果.信息列表)
        
        # 如果 API 配置有致命错误，不继续验证
        if api结果.是否有错误():
            return 总结果
        
        # 验证模型配置
        模型配置 = 配置管理器.获取模型配置()
        if not 模型配置:
            总结果.添加错误("无法读取 model_config.toml")
            return 总结果
        
        模型结果 = cls.验证模型配置(模型配置, api配置)
        总结果.错误列表.extend(模型结果.错误列表)
        总结果.警告列表.extend(模型结果.警告列表)
        总结果.信息列表.extend(模型结果.信息列表)
        
        # 验证运行时配置
        运行时配置 = 配置管理器.获取运行时配置()
        if 运行时配置:
            运行时结果 = cls.验证运行时配置(运行时配置)
            总结果.错误列表.extend(运行时结果.错误列表)
            总结果.警告列表.extend(运行时结果.警告列表)
            总结果.信息列表.extend(运行时结果.信息列表)
        
        return 总结果


def 验证配置并退出如果有错误(配置管理器) -> bool:
    """
    验证配置，如果有错误则打印并返回 False
    
    返回:
        bool: True 表示验证通过，False 表示有错误
    """
    logger.info("正在验证配置文件...")
    结果 = 配置验证器.验证所有配置(配置管理器)
    结果.打印结果()
    
    if 结果.是否有错误():
        logger.error("配置验证失败，请修复上述错误后重新启动")
        return False
    
    if 结果.是否有警告():
        logger.warning("配置验证发现警告，建议检查配置文件")
    
    return True


if __name__ == "__main__":
    """测试配置验证器"""
    from 模块.配置管理器 import 获取配置管理器
    
    管理器 = 获取配置管理器()
    结果 = 配置验证器.验证所有配置(管理器)
    结果.打印结果()
    
    if 结果.是否有错误():
        print("\n[失败] 配置验证失败")
        exit(1)
    else:
        print("\n[成功] 配置验证通过")
