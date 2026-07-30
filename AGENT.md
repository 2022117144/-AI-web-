# 万象AI + 智创工具 — 项目规则

## 项目定位
自动化视频工作流平台。合并了智创AI Tools后端 + 万象AI平台。

## 技术栈
- 后端：Python FastAPI，单端口 8765
- 前端：纯 HTML/CSS/JS（无框架），web_frontend/
- 数据库：JSON 文件存储（data/ 目录）
- 依赖服务：insMind 后端 (8005) + insmind2api (5105)

## 启动方式
```bash
cd D:\万象AI改
python run.py
```
run.py 会自动启动 insMind (8005)、insmind2api (5105) 和主服务 (8765)。

## 项目结构
- `run.py` — 主入口，合并智创+万象路由，启动所有服务
- `zc_backend/` — 智创后端（server.py, pipeline.py, handlers.py, llm.py 等）
- `web_frontend/` — 前端静态文件（index.html, zc_index.html, css/, js/）
- `data/` — JSON 数据文件（projects.json, pipeline_runs.json, llm_config.json 等）
- `data/project_content/` — 项目内容（图片、视频提示词、文案等）

## 端口
- 8765 — 主服务（万象AI + 智创合并）
- 8005 — insMind 后端
- 5105 — insmind2api 中继

## 注意
- 运行前清除 PYTHONPATH/PYTHONHOME 防版本冲突
- 依赖 venv 是系统 Python 3.11，不是独立 venv
- 启动用 `/d/万象AI改/.venv/Scripts/python.exe`，不用系统 `python`（指向 Hermes venv）

## 端口占用处理（铁律）
遇到端口被占，**先自己杀，不问用户**。

查端口用 PowerShell 或 cmd findstr，别用 git-bash 的 grep（管道编码有问题会漏结果）：
```powershell
powershell -Command "Get-NetTCPConnection -LocalPort <端口> -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess,State"
```
```cmd
netstat -ano | findstr ":<端口>"
```
杀掉：
```bash
netstat -ano | findstr ":<端口>" | awk '{print $NF}' | sort -u | while read pid; do
  [ "$pid" -gt 0 ] 2>/dev/null && taskkill -f -pid $pid 2>/dev/null
done
```
杀不掉（幽灵 socket）用 Python 抢占：
```python
python -c "import socket; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('0.0.0.0',<端口>)); s.close()"
```