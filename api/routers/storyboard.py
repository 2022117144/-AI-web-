"""
分镜路由 — 分镜管理
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from zc_backend import handlers as handlers_mod

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