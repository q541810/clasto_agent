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

### 第一步：准备环境

#### 1.1 安装 Python

**Windows 用户：**
1. 访问 [Python 官网](https://www.python.org/downloads/)
2. 下载 Python 3.10 或更高版本
3. 安装时**务必勾选** "Add Python to PATH"
4. 安装完成后，打开命令提示符（CMD）或 PowerShell，输入 `python --version` 检查是否安装成功

**macOS/Linux 用户：**
```bash
# macOS (使用 Homebrew)
brew install python@3.10

# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3-pip

# 检查版本
python3 --version
```

#### 1.2 下载项目

```bash
# 克隆项目到本地
git clone https://github.com/q541810/clasto_agent.git
cd clasto_agent

# 或者直接下载 ZIP 并解压
```

#### 1.3 安装依赖

```bash
# Windows
pip install -r requirements.txt

# macOS/Linux
pip3 install -r requirements.txt
```

如果安装速度慢，可以使用国内镜像：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

### 第二步：获取 AI 模型 API

你需要一个 AI 模型的 API Key。推荐以下平台（选一个即可）：

#### 选项 1：硅基流动（仅为示例，好贵的，不太推荐哦）
1. 访问 [硅基流动](https://cloud.siliconflow.cn/)
2. 注册账号并登录
3. 进入控制台 → API 密钥 → 创建新密钥
4. 复制 API Key（格式类似：`sk-xxxxxxxxxxxxx`）

#### 选项 2：DeepSeekAPI开放平台（新出的v4 flash便宜的很奥，推荐哦）
1. 访问 [DeepSeekAPI开放平台](https://platform.deepseek.com/)
2. 注册并充值）
3. 创建 API Key

#### 选项 3：其他兼容 OpenAI 格式的平台
- DeepSeek、智谱 AI、月之暗面等都可以

---

### 第三步：配置文件设置

#### 3.1 复制配置模板

**Windows（PowerShell）：**
```powershell
Copy-Item "配置文件模板\api_config.toml" "配置文件\api_config.toml"
Copy-Item "配置文件模板\model_config.toml" "配置文件\model_config.toml"
Copy-Item "配置文件模板\runtime_config.toml" "配置文件\runtime_config.toml"
Copy-Item "模块\适配器\napcat\配置文件模板\config.toml" "模块\适配器\napcat\config.toml"
```

**macOS/Linux：**
```bash
cp 配置文件模板/api_config.toml 配置文件/api_config.toml
cp 配置文件模板/model_config.toml 配置文件/model_config.toml
cp 配置文件模板/runtime_config.toml 配置文件/runtime_config.toml
cp 模块/适配器/napcat/配置文件模板/config.toml 模块/适配器/napcat/config.toml
```

#### 3.2 填写 API 配置

打开 `配置文件/api_config.toml`，填入你的 API Key：

```toml
["现有模型厂商"]
# 把下面的 "换成你自己的api_key" 替换成你在第二步获取的 API Key
硅基流动 = { url = "https://api.siliconflow.cn/v1", api_key = "sk-你的真实API_KEY" }

["模型配置"]
# 这里配置你要使用的模型
"deepseek-V3.2" = { "厂商" = "硅基流动", "模型id" = "deepseek-ai/DeepSeek-V3.2" }
```

**常用模型推荐：**
- **DeepSeek-V3**：性价比高，适合日常对话
- **Qwen2.5-72B**：阿里出品，中文理解好
- **GPT-4**：最强但贵，需要 OpenAI### 3.3 配置模型行为

打开 `配置文件/model_config.toml`：

```toml
["回复模型"]
model = "deepseek-V3.2"  # 使用你在 api_config.toml 中配置的模型名
system_prompt = "你是一个乐于助人的AI助手"  # 可以自定义机器人性格
max_history = 20  # 记住最近 20 条对话

["规划模型"]
model = "deepseek-V3.2"  # 用于决定调用什么工具
system_prompt = "你是一个对话规划器。请根据用户意图选择工具。"

["筛选模型"]
model = ""  # 留空表示不使用筛选（推荐新手先留空）
```

#### 3.4 配置机器人名字

打开 `配置文件/runtime_config.toml`：

```toml
bot的名字 = "小助手"  # 改成你喜欢的名字
模型调用自动重试次数 = 1

["群聊回复逻辑"]
mode = "直接规划"  # 新手推荐用 "直接规划"，简单直接
关闭规划模型 = false

["群聊回复优化"]
at必回复 = true  # 被 @ 时一定回复
提及关键词 = ["小助手", "在吗"]  # 提到这些词也会回复
```

---

### 第四步：安装并配置 Napcat

Napcat 是连接 QQ 的桥梁，必须安装。

#### 4.1 下载 Napcat

访问 [Napcat 官方仓库](https://github.com/NapNeko/NapCatQQ/releases)，下载最新版本。

#### 4.2 启动 Napcat

1. 解压下载的文件
2. 运行 Napcat（具体方法见 Napcat 官方文档）
3. 登录你的 QQ 机器人账号
4. 在 Napcat 配置中启用 **WebSocket 正向连接**，端口设为 `3001`

#### 4.3 配置 Napcat 连接

打开 `模块/适配器/napcat/config.toml`：

```toml
connection_mode = "forward"  # 正向连接模式

["napcat_server"]
host = "localhost"  # Napcat 运行在本机
port = 3001  # Napcat 的 WebSocket 端口（需要和 Napcat 配置一致）
token = ""  # 如果 Napcat 设置了 token，填在这里

["clasto_agent"]
host = "localhost"
port = 8081  # 本程序监听的端口，不用改

[session_filter.groups]
mode = "whitelist"  # 白名单模式，只回复指定的群
list = [123456789, 987654321]  # 把这里改成你要让机器人工作的群号

[session_filter.users]
mode = "none"  # 私聊不筛选，所有人都能聊
list = []
```

**如何获取群号？**
- 在 QQ 群里点击群头像 → 群设置 → 群号码

---

### 第五步：启动机器人

#### 5.1 先启动 Napcat

确保 Napcat 已经运行并登录了 QQ。并且设置完毕（设置过程详见4.3配置 Napcat 连接）

#### 5.2 启动 Clasto Agent

```bash
# Windows
python main.py

# macOS/Linux
python3 main.py
```

#### 5.3 检查启动日志

如果看到以下日志，说明启动成功：
```
✓ 配置验证通过
✓ WebSocket 服务端已在 ws://localhost:8081 启动
✓ 适配器已连接: ('127.0.0.1', xxxxx)
```

#### 5.4 测试机器人

在私聊里发送消息（记得看看适配器配置文件哦，别发现没配置白名单）：
```
你好
```

如果机器人回复了，恭喜你成功了！🎉

---

### 常见问题

**Q: 提示 "配置文件 API Key 未修改"**  
A: 你忘记把 `api_config.toml` 里的 `换成你自己的api_key` 改成真实的 API Key 了。

**Q: 提示 "适配器未连接"**  
A: 检查 Napcat 是否正常运行，以及端口配置是否一致（默认 3001）。

**Q: 机器人不回复消息**  
A: 检查群号是否在白名单里，或者把 `mode` 改成 `"none"` 试试。

**Q: 提示 "模型调用失败"**  
A: 检查 API Key 是否正确，是否有余额，网络是否正常。

**Q: 想看更详细的日志**  
A: 使用调试模式启动：`python main.py -debug`

---

### 进阶配置

启动成功后，你可以：
- 调整 `system_prompt` 来改变机器人性格
- 启用 `筛选模型` 来减少群聊刷屏
- 开发自己的插件来扩展功能
- 配置多个模型厂商实现负载均衡

详细文档请查看 [AGENTS.(AGENTS.md)

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
