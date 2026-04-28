# Clasto Agent

一个让 AI 机器人"会思考、能干活"的 QQ 聊天机器人框架。

## 特点

- **三阶段处理**：规划 → 工具执行 → 回复，让 AI 的决策过程清晰可控
- **插件系统**：通过钩子（Hook）机制随意扩展功能，无需修改核心代码
- **工具自动注册**：注册工具后自动生成 AI 可理解的调用说明
- **群聊智能筛选**：可选的筛选模型，避免 AI 在群里瞎回复刷屏
- **异步架构**：基于 asyncio + WebSocket，支持高并发消息处理

## 工作流程

```
QQ用户 → Napcat → 适配器(正向WS) → 主程序(WS:8081)
  ↓
规划模型(决定调用什么工具)
  ↓
执行工具(搜索/查群/发消息等)
  ↓
回复模型(生成最终回复)
  ↓
发送回用户
```

每个环节都有插件钩子可以介入修改。

## 快速开始

### 1. 环境要求

- Python 3.10+
- Napcat（QQ 机器人协议端）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

首次运行需要从模板创建配置文件：

```bash
# 复制配置文件模板
cp 配置文件模板/api_config.toml 配置文件/api_config.toml
cp 配置文件模板/model_config.toml 配置文件/model_config.toml
cp 配置文件模板/runtime_config.toml 配置文件/runtime_config.toml
cp 模块/适配器/napcat/配置文件模板/config.toml 模块/适配器/napcat/config.toml
```

#### 配置说明

**api_config.toml** - API 厂商和模型配置

```toml
["现有模型厂商"]
硅基流动 = { url = "https://api.siliconflow.cn/v1", api_key = "你的API_KEY" }

["模型配置"]
"deepseek-V3.2" = { "厂商" = "硅基流动", "模型id" = "deepseek-ai/DeepSeek-V3.2" }
```

**model_config.toml** - 模型行为配置

```toml
["回复模型"]
model = "deepseek-V3.2"  # 对应 api_config.toml 中的模型名
system_prompt = "你是一个乐于助人的AI助手"
max_history = 20

["规划模型"]
model = "deepseek-V3.2"  # 留空则跳过规划阶段
system_prompt = "你是一个对话规划器。请根据用户意图选择工具。"

["筛选模型"]
model = "deepseek-V3.2"  # 用于群聊回复优化，留空则不筛选
```

**runtime_config.toml** - 运行时逻辑配置

```toml
bot的名字 = "小助手"
模型调用自动重试次数 = 1

["群聊回复逻辑"]
mode = "群聊回复优化"  # 或 "直接规划"
关闭规划模型 = false

["群聊回复优化"]
at必回复 = true
提及关键词 = ["小助手", "在吗"]
```

**模块/适配器/napcat/config.toml** - Napcat 连接配置

```toml
connection_mode = "forward"  # 正向WS模式

["napcat_server"]
host = "localhost"
port = 3001  # Napcat 的 WS 端口
token = ""

[session_filter.groups]
mode = "whitelist"  # 白名单模式
list = [123456789]  # 允许的群号列表
```

### 4. 启动

```bash
python main.py
```

启用调试模式（查看更多日志内容，比如包括内置提示词之类的模型原输入、打开消息分割后每次流式收到的token）：

```bash
python main.py -debug
```

## 内置工具

| 工具名      | 说明             |
| -------- | -------------- |
| 回复工具     | 调用回复模型生成回复     |
| 发送消息工具   | 直接向指定会话发送消息    |
| 查询群列表工具  | 查询当前账号已加入的所有群聊 |
| 获取会话消息工具 | 获取某个群聊或私聊的最近消息 |
| 获取当前时间工具 | 获取当前系统时间和星期    |
| 联网搜索工具   | 使用 Bing 进行联网搜索 |
| 多轮执行工具   | 请求进入下一轮规划      |

## 插件开发

### 目录结构

```
插件/
  我的插件/
    plugin.toml    # 插件元信息 + 默认配置
    main.py        # 插件入口
插件配置/
  我的插件.toml    # 用户配置覆写（可选）
```

### 插件示例

**plugin.toml**

```toml
[plugin]
name = "我的插件"
version = "1.0.0"
description = "示例插件"
author = "你的名字"
priority = 100  # 钩子执行优先级，数字越小越先执行

[plugin.config]
api_key = ""
max_count = 5
```

**main.py**

```python
async def 入口(上下文):
    """插件入口函数，启动时调用一次"""

    # 注册自定义工具
    async def 我的工具(关键词: str):
        return f"搜索结果: {关键词}"

    上下文.注册工具(
        名称="我的工具",
        工具函数=我的工具,
        别名=["搜索"],
        参数说明={"关键词": "搜索关键词"},
        说明="示例工具"
    )

    # 注册钩子
    async def 修改回复(回复内容):
        return 回复内容 + " [来自插件]"

    上下文.注册钩子("on_post_reply", 修改回复)
```

### 可用钩子

| Hook                 | 触发时机       | 返回值            |
| -------------------- | ---------- | -------------- |
| `on_load`            | 插件加载完成     | 无              |
| `on_unload`          | 插件卸载       | 无              |
| `on_message_receive` | 消息进入主程序    | 消息数据或 None(拦截) |
| `on_message_enqueue` | 消息进入聊天流队列前 | 消息数据或 None(拦截) |
| `on_pre_plan`        | 规划模型调用前    | 可修改对话历史        |
| `on_post_plan`       | 规划输出后      | 可修改工具调用列表      |
| `ost_tool`           | 工具执行后      | 可修改工具结果        |
| `on_pre_reply`       | 回复模型调用前    | 可修改提示词         |
| `on_post_reply`      | 回复生成后      | 可修改回复内容        |
| `on_send_message`    | 消息发送前      | 回复数据或 None(拦截) |

### 插件上下文 API

```python
上下文.注册工具(名称, 工具函数, 别名, 参数说明, 说明, 是否回复工具)
上下文.注册钩子(hook名, 回调)
上下文.调用适配器API(action, params)
上下文.获取聊天流(chat_id)
上下文.发送消息(chat_id, chat_type, message)
上下文.获取配置(键=None)
```

## 目录结构

```
clasto-agent/
├── main.py                    # 主入口
├── requirements.txt           # 依赖列表
├── AGENTS.md                  # 项目详细注解
├── 模块/
│   ├── 聊天管理器.py          # 聊天流管理
│   py          # 工具注册与执行
│   ├── 插件管理器.py          # 插件系统核心
│   ├── openai格式模型调用.py  # 模型调用封装
│   ├── reading_config.py      # 配置读取
│   ├── 启动适配器.py          # 适配器启动
│   └── 适配器/
│       └── napcat/            # Napcat 适配器
├── 配置文件/                  # 实际配置（需自行创建）
├── 配置文件模板/              # 配置文件模板
├── 插件/                      # 插件目录
│   └── 示例插件/
└── 插件配置/                  # 插件配置覆写
```

## 高级功能

### 消息分割器

在 `runtime_config.toml` 中启用：

```toml
["消息分割器"]
启用 = true  # 启用后回复模型使用流式输出，遇到换行或句号时分段发送
```

### 群聊回复优化

通过筛选模型预判是否需要回复，避免无意义响应：

```toml
["群聊回复逻辑"]
mode = "群聊回复优化"

["群聊回复优化"]
at必回复 = true
提及关键词 = ["小助手", "在吗"]
上下文条数 = 7
```

### 关闭规划模型

如果不需要工具调用能力，可以关闭规划模型直接回复：

```toml
["群聊回复逻辑"]
关闭规划模型 = true  # 警告: 将无法使用工具能力
```

## 常见问题

**Q: 端口 8081 被占用怎么办？**  
A: 检查是否已有主程序在运行，或修改 `main.py` 中的端口号。

**Q: Napcat 连接失败？**  
A: 检查 `模块/适配器/napcat/config.toml` 中的 host 和 port 是否与 Napcat 配置一致。

**Q: 插件加载失败？**  
A: 查看日志中的错误信息，确保 `plugin.toml` 格式正确且 `main.py` 包含 `入口()` 函数。

**Q: 如何查看完整日志？**  
A: 使用 `python main.py -debug` 启动调试模式。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源协议。

## 致谢

- [Napcat](https://github.com/NapNeko/NapCatQQ) - QQ 机器人协议端
- Maibot - 写适配器的时候借鉴了一小点
- 感谢所有贡献者
