# 万象AI + 智创工具 — 会话交接

## 当前状态 (2026-07-30)
- 项目已稳定运行，后端 8765 端口（FastAPI）
- 依赖：insMind 后端 (8005) + insmind2api (5105)

## 项目结构
```
万象AI改/
├── run.py                  # 主入口：合并智创+万象路由，启动所有服务
├── AGENT.md                # 项目规则
├── handoff.md              # 会话交接（本文件）
├── IDEA.md                 # "自动化视频工作流"
├── _fix_rename.py          # 临时修复脚本
├── zc_backend/             # 智创后端（核心流水线引擎）
│   ├── server.py           #   智创 FastAPI 应用 (1563行)
│   ├── pipeline.py         #   流水线引擎 (585行) — 步骤定义、Handler注册、PipelineRun
│   ├── handlers.py         #   外部API Handler (359行) — PhotoGPT/insMind/BGM
│   ├── llm.py              #   LLM 客户端
│   ├── prompts.py          #   系统提示词管理
│   ├── characters.py       #   角色管理
│   ├── scenes.py           #   场景管理
│   ├── _edge_tts_wrapper.py#   edge-tts 本地TTS包装
│   └── data/               #   JSON 数据文件
│       ├── pipeline_runs.json
│       ├── projects.json
│       └── tts_output/
├── api/                    # 万象AI路由层（引用 E:\万象AI-2改\src\core）
│   ├── server.py           #   万象AI FastAPI 应用
│   └── routers/            #   路由模块
│       ├── config.py / llm.py / image.py / video.py
│       ├── copy.py / project.py / tools.py
│       ├── pipeline.py     #   流水线 API（/api/pipeline/run）
│       └── storyboard.py   #   分镜 API（/api/storyboard/generate-frames/video）
├── core/                   # 引用 E:\万象AI-2改\src\core 的代理
│   ├── project_manager.py
│   └── copy_tools.py
├── web_frontend/           # 前端静态文件
│   ├── index.html          #   万象AI首页
│   ├── zc_index.html       #   智创工具首页
│   ├── config.html         #   配置页
│   ├── css/style.css
│   └── js/app.js
└── docs/                   # 文档
```

## 流水线步骤（7步）
1. **style_prompt** — 风格提示词（可选）
2. **script** — 文案生成（LLM）
3. **audio_srt** → 实际用 `storyboard_prompts` + `script_audio` — 分镜提示词 + 旁白TTS
4. **photogpt_images** — PhotoGPT 生成分镜图片
5. **insmind_video** — insMind 生成视频片段
6. **ffmpeg_merge** — ffmpeg 拼接（框架）
7. **bgm_send** — 加BGM+发送（桩）

## 关键决策
- 双路由合并：run.py 合并 zc_backend/server.py 和 api/server.py 的路由
- 流水线引擎在 zc_backend/pipeline.py，万象API的 /api/pipeline/run 引用 core/pipeline_mod（来自 E:\万象AI-2改\src\core）
- 依赖服务在 run.py 启动时自动拉起（DETACHED_PROCESS）

## 已知问题/坑
- 8765 端口被系统幽灵进程占用时需手动清理（AGENT.md 有杀端口流程）
- run.py 依赖 `.venv/Scripts/python.exe` 而非系统 python
- 智创流水线（zc_backend/pipeline.py）和万象流水线（api/routers/pipeline.py → core/pipeline_mod）是两套，但底层 handler 注册在 server.py
- PhotoGPT 轮询 60s 间隔 × 4 次 ≈ 4 分钟超时
- insMind 视频轮询 60s 间隔 × 120 次 ≈ 2 小时超时
- 自动注册账号后 3s 等待再重试视频生成