"""
万象AI改 — FastAPI 启动入口
使用 uvicorn.run 启动服务，监听 8765 端口。
"""
import sys
import os

# 将项目根目录加入 sys.path（确保 api.server 可被导入）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        log_level="info"
    )