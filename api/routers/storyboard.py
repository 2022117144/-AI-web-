"""
分镜路由 — 分镜管理
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

# 将项目根目录和万象AI-2改源码加入路径
PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)
WANXIANG_2_SRC = r"E:\万象AI-2改\src"
if WANXIANG_2_SRC not in sys.path:
    sys.path.insert(0, WANXIANG_2_SRC)

from core import handlers_mod

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"])


class GenerateFramesRequest(BaseModel):
    shots: list = Field(..., description="分镜列表")
    aspect_ratio: str = Field(default="16:9", description="宽高比")


@router.post("/generate-frames")
async def generate_frames(req: GenerateFramesRequest):
    """生成分镜首帧/尾帧图片"""
    try:
        result = handlers_mod.photogpt_images_handler(
            {}, {"shots": req.shots, "aspect_ratio": req.aspect_ratio}
        )
        return {"code": 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GenerateVideoRequest(BaseModel):
    shots: list = Field(..., description="分镜列表")
    shot_frames: dict = Field(default={}, description="已有图片帧")
    model: str = Field(default="Pixverse-V6.0", description="视频模型")
    ratio: str = Field(default="16:9", description="比例")
    resolution: str = Field(default="360p", description="分辨率")
    duration: int = Field(default=10, description="视频时长(秒)")


@router.post("/generate-video")
async def generate_video(req: GenerateVideoRequest):
    """生成分镜视频"""
    try:
        result = handlers_mod.insmind_video_handler(
            {}, {
                "shots": req.shots,
                "shot_frames": req.shot_frames,
                "model": req.model,
                "ratio": req.ratio,
                "resolution": req.resolution,
                "duration": req.duration,
            }
        )
        return {"code": 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))