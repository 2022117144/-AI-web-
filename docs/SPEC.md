---
created: 2026-07-22
updated: 2026-07-22
---

# 万象AI改 — Web-First 重构项目

> 给万象AI-2改（PyQt5 桌面应用）加一层 HTTP API，开发阶段用 Web 前端调试，稳定后前端可换回 PyQt5。

## 项目身份

在 `E:\万象AI改` 新建项目，给 `万象AI-2改\src\` 的现有业务逻辑包一层 FastAPI 接口，让 Web 前端能调。业务逻辑不改，只在上面加 HTTP 层。

## 核心决策

| 决策 | 原因 |
|------|------|
| 业务逻辑不动，直接 import 万象AI-2改 的函数 | 代码已写好，不需要重写 |
| API 层用 FastAPI | Python 生态，轻量，自动生成 OpenAPI 文档 |
| 开发阶段用 Web 前端（Vue/React） | 热更新，F5 刷新看效果，调试快 |
| 交付阶段前端可换 PyQt5（直接 import core/） | 原生桌面应用，不依赖 HTTP |
| 模型配置页面单独重做 UI | 用户要求美观、专业的配置界面 |
| 视频模型硬编码用 insMind | 用户指定，但地址读配置 |
| 图片模型硬编码用 PhotoGPT | 用户指定，但地址读配置 |
| LLM 不固定供应商 | 放可自定义接口地址 + Key 让用户填 |

## 反向决策

- ❌ 不重写任何已有业务逻辑
- ❌ 不一次性暴露所有功能（只做配置 + 模型对接）
- ❌ 不引入新框架（保持 Python 3.10 + PyQt5 兼容）
- ❌ 不修改 万象AI-2改 原有代码（除非必要）
- ❌ 不做多用户并发（保持单用户设计）

## 模块边界

| 模块 | 职责 | 不可越界 |
|------|------|---------|
| `api/` | FastAPI 路由，调 万象AI-2改 的函数 | 不写业务逻辑 |
| `api/routers/config.py` | 配置读写接口 | 不涉及推理 |
| `api/routers/llm.py` | LLM 推理接口 | 不涉及图片/视频 |
| `api/routers/image.py` | 图片生成接口 | 不涉及 LLM |
| `api/routers/video.py` | 视频生成接口 | 不涉及 LLM |
| `web_frontend/` | 开发阶段 Web 前端 | 只调 API，不直接调业务逻辑 |
| `pyqt5_frontend/` | 交付阶段 PyQt5 前端 | 直接 import core/ |

## ADR 索引

（待后续执行中补充）