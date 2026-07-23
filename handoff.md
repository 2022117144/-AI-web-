# 万象AI改 — Handoff 会话状态

## 项目身份
给万象AI-2改（PyQt5 桌面应用）加一层 HTTP API，开发阶段用 Web 前端调试，交付阶段可换回 PyQt5。

## 当前状态 (2026-07-23)

### ✅ 已完成
- **后端 API 层**: FastAPI 监听 8765，9 个路由模块
  - `config` — 配置读写（GET/PUT /api/config）
  - `llm` — LLM 推理（POST /api/llm/chat）
  - `image` — PhotoGPT 图片生成（POST /api/image/generate）
  - `video` — insMind 视频生成（POST /api/video/generate）
  - `copy` — 文案生成/修改/保存/分镜生成（POST /api/copy/*）
  - `project` — 项目管理（POST /api/project/create, GET /list, DELETE /delete, GET /quota）
  - `tools` — AI工具箱列表/执行（GET /api/tools/list, POST /execute）
  - `pipeline` — 流水线执行（POST /api/pipeline/run, GET /steps）
  - `storyboard` — 分镜图片/视频生成（POST /api/storyboard/*）

- **core/ 业务逻辑层**: 从 zctools 封装，供 api/ 和 pyqt5 共用
  - `core/__init__.py` — 统一导入入口
  - `core/copy_tools.py` — 文案生成/修改/保存/分镜
  - `core/project_manager.py` — 项目 CRUD + 额度刷新

- **Web 前端**:
  - `index.html` — 主界面，全部按钮已接实
    - 文案 AI 生成 ✅（改走 `/api/copy/generate`）
    - 文案 AI 修改 ✅（`/api/copy/modify`）
    - 保存文案 ✅（`/api/copy/save`）
    - 生成分镜 ✅（自动跳转分镜页 + 渲染分镜列表 + SRT 字幕）
    - 分镜选择/详情查看 ✅
    - 生成首帧 ✅（`/api/storyboard/generate-frames`）
    - 流水线执行 ✅（`/api/pipeline/run`）
    - 新建项目/加载项目列表 ✅
    - 刷新额度 ✅
    - 切换主题 ✅
    - 工具栏按钮 → Toast 提示待接入
    - AI工具箱 → Toast 提示开发中
  - `config.html` — 配置页，5 tab 动态加载 ✅

### 🔄 待完成
- **批量功能按钮**（一键成片、批量改写、批量推理、批量语音等）— 需要后端加批量处理路由
- **AI工具箱具体功能**（AI数字人、VD错峰视频管理）— 后端待实现
- **流水线停止/刷新** — 后端需要实现取消和状态查询
- **分镜尾帧/视频生成** — 依赖后端 insmind 连通性
- **创作工具**（视频下载、字幕提取、音频提取等）— 依赖 ffmpeg 集成
- **运行日志面板** — 需要后端日志流接口
- **pyqt5_frontend/ 目录** — 交付阶段 PyQt5 前端，空

### 关键决策
- 业务逻辑不重写，直接从 `万象AI-2改\src` import
- `core/` 封装 zctools 智创工具的纯逻辑，PyQt5 零依赖
- 所有按钮用 `data-p` + CSS class 切换页面，不用内联 style
- 所有 API 响应格式统一 `{code: 200, data: {...}}`

### 已知问题
- `zctools/zc_llm.py` 有自己的 LLM 配置（llm_config.json），与 `A0_config` 是两套系统
- 视频生成依赖 insMind 后端可用性
- 分镜图片生成依赖 PhotoGPT 后端可用性