"""
万象AI + 智创工具 合并后端 — 单端口 8765
"""
import sys, os

ZC_DIR = os.path.join(os.path.dirname(__file__), 'zc_backend')
sys.path.insert(0, ZC_DIR)

# 加载智创依赖
import pipeline
import llm
import handlers
import prompts
import characters

# 加载智创 app
from server import app as zc_app

# 加载万象 app
from api.server import app as wx_app

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="万象AI + 智创工具")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 直接合并路由列表
skip = {'/', '/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc',
        '/css/{file}', '/js/{file}', '/static'}
seen = set()
for r in zc_app.routes + wx_app.routes:
    path = getattr(r, 'path', '')
    methods = tuple(getattr(r, 'methods', ['GET']) or ['GET'])
    key = (path, methods)
    if path not in skip and key not in seen:
        app.router.routes.append(r)
        seen.add(key)

# 静态文件
FE_DIR = os.path.join(os.path.dirname(__file__), 'web_frontend')

@app.get("/")
async def root():
    return FileResponse(os.path.join(FE_DIR, "index.html"))

@app.get("/config.html")
async def config():
    return FileResponse(os.path.join(FE_DIR, "config.html"))

@app.get("/css/{file}")
async def css(file: str):
    return FileResponse(os.path.join(FE_DIR, "css", file))

@app.get("/js/{file}")
async def js(file: str):
    return FileResponse(os.path.join(FE_DIR, "js", file))

@app.get("/zc/")
async def zc_root():
    return FileResponse(os.path.join(FE_DIR, "zc_index.html"))

@app.get("/zc/{rest:path}")
async def zc_static(rest: str):
    fp = os.path.join(FE_DIR, rest)
    if os.path.exists(fp):
        return FileResponse(fp)
    return FileResponse(os.path.join(FE_DIR, "zc_index.html"))

if __name__ == "__main__":
    import subprocess, socket, time, atexit, signal

    _children = []

    def check_port(port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            return result == 0
        except:
            return False

    def start_service(name, port, cwd, cmd, env_clear=None, pip_install=None):
        if check_port(port):
            print(f"  {name} (: {port}) ✅ 已在运行")
            # 找到已运行进程的 PID，加入 children 列表以便退出时一并清理
            try:
                r = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=5)
                raw = r.stdout.decode("utf-8", errors="replace")
                for line in raw.splitlines():
                    if f":{port} " in line and "LISTENING" in line:
                        pid = line.strip().split()[-1]
                        if pid.isdigit():
                            _children.append(("pid", int(pid)))
                            print(f"    → 已关联 PID={pid}，退出时一并清理")
                        break
            except: pass
            return None
        if pip_install:
            try:
                subprocess.run([cmd[0], "-m", "pip", "install", "-q"] + pip_install,
                    cwd=cwd, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except: pass
        env = os.environ.copy()
        for k in (env_clear or []):
            env.pop(k, None)
        proc = subprocess.Popen(cmd, cwd=cwd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
        print(f"  {name} (: {port}) 🚀 启动中 (PID={proc.pid})")
        _children.append(proc)
        return proc

    def cleanup():
        for proc in _children:
            if isinstance(proc, tuple) and proc[0] == "pid":
                # 按 PID 杀（已运行的服务）
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(proc[1])],
                        capture_output=True, timeout=5)
                except: pass
            elif proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    try: proc.kill()
                    except: pass

    atexit.register(cleanup)

    # 启动辅服务
    start_service(
        "insMind后端", 8005,
        r"E:\视频生成\dreamina-auto-register-main\backend",
        [r"E:\视频生成\dreamina-auto-register-main\backend\.venv_win\Scripts\python.exe", "run.py"],
        env_clear=["PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV"],
        pip_install=["curl_cffi", "cffi"],
    )
    start_service(
        "insmind2api", 5105,
        r"E:\视频生成\dreamina-auto-register-main\insmind2api",
        ["node", "dist/index.js"],
    )

    # 启动主服务
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
    finally:
        cleanup()