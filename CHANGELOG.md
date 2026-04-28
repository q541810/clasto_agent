# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2024-04-28

### Added
- 初始版本发布
- 三阶段消息处理架构（规划 → 工具执行 → 回复）
- 完整的插件系统，支持钩子机制和自定义工具注册
- Napcat 适配器，支持正向/反向 WebSocket 连接
- 内置工具：
  - 回复工具
  - 发送消息工具
  - 查询群列表工具
  - 获取会话消息工具
  - 获取当前时间工具
  - 联网搜索工具（基于 Bing）
  - 多轮执行工具
- 群聊回复优化功能（可选的筛选模型）
- 消息分割器（流式输出分段发送）
- 配置文件系统：
  - API 配置（api_config.toml）
  - 模型配置（model_config.toml）
  - 运行时配置（runtime_config.toml）
  - 适配器配置（napcat/config.toml）
- 会话筛选（群聊/私聊独立白名单/黑名单）
- 调试模式（-debug 参数）
- 完整的日志系统
- 异步架构，支持高并发消息处理

### Documentation
- README.md - 项目介绍和快速开始指南
- AGENTS.md - 详细的项目架构和开发文档
- 配置文件模板和示例

[Unreleased]: https://github.com/q541810/clasto_agent/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/q541810/clasto_agent/releases/tag/v1.0.0
