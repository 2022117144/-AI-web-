"""
万象AI改 — FastAPI 服务器入口
监听 8765 端口，带 CORS 支持。
"""
import sys
import os

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import config as config_router
from api.routers import llm as llm_router
from api.routers import image as image_router
from api.routers import video as video_router
from api.routers import copy as copy_router
from api.routers import project as project_router
from api.routers import tools as tools_router
from api.routers import pipeline as pipeline_router
from api.routers import storyboard as storyboard_router

app = FastAPI(
    title="万象AI改 API",
    description="万象AI改 配置管理 API 服务",
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
app.include_router(copy_router.router)
app.include_router(project_router.router)
app.include_router(tools_router.router)
app.include_router(pipeline_router.router)
app.include_router(storyboard_router.router)