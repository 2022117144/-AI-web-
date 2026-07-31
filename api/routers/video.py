"""
视频生成路由

调用 insMind 视频生成后端。
地址硬编码为 localhost:8005（与 zc_backend/handlers.py 一致）。
"""
import sys
import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/video", tags=["video"])

# insMind 地址（与 zc_backend/handlers.py 一致）
INSMIND_URL = "http://localhost:8005"


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., description="生成视频的提示词")
    model: str = Field(default="insMind", description="模型名称（当前硬编码为 insMind）")


class VideoGenerateResponse(BaseModel):
    success: bool = Field(..., description="是否生成成功")
    video_url: str = Field(default="", description="生成的视频 URL")
    error: str = Field(default="", description="错误信息（失败时）")
    model: str = Field(default="insMind", description="实际使用的模型")


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(req: VideoGenerateRequest):
    """视频生成接口"""
    print(f"[insMind] 提示词: {req.prompt}")

    try:
        resp = httpx.post(
            f"{INSMIND_URL}/api/video/generate",
            json={
                "prompt": req.prompt,
                "model": "insMind",
            },
            timeout=120,
        )
        data = resp.json()

        if not data.get("success"):
            return VideoGenerateResponse(
                success=False,
                video_url="",
                error=data.get("error", "视频生成失败"),
                model="insMind",
            )

        video_url = data.get("video_url", "")
        if not video_url:
            return VideoGenerateResponse(
                success=False,
                video_url="",
                error="生成成功但未返回视频 URL",
                model="insMind",
            )

        return VideoGenerateResponse(
            success=True,
            video_url=video_url,
            error="",
            model="insMind",
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"insMind 后端请求失败: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"视频生成失败: {str(e)}",
        )