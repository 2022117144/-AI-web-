"""
万象AI改 — FastAPI 服务器入口
监听 8765 端口，带 CORS 支持。
"""
import sys
import os

# 将万象AI-2改 源码路径加入 sys.path
sys.path.insert(0, r'E:\万象AI-2改\src')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import config as config_router
from api.routers import llm as llm_router
from api.routers import image as image_router
from api.routers import video as video_router

app = FastAPI(
    title="万象AI改 API",
    description="万象AI-2改 配置管理 API 服务",
    version="1.0.0"
)

# CORS 配置 — 允许所有来源（开发阶段）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(config_router.router)
app.include_router(llm_router.router)
app.include_router(image_router.router)
app.include_router(video_router.router)

# 挂载静态文件（Web 前端配置页面）
import os
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web_frontend')
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")


@app.get("/")
async def root():
    return {
        "service": "万象AI改 API",
        "version": "1.0.0",
        "endpoints": {
            "GET  /api/config": "返回所有配置项",
            "PUT  /api/config": "更新配置项（JSON body: {updates: {...}}）"
        }
    }