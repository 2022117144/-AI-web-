"""
视频生成路由

调用 insMind 视频生成后端。
硬编码模型为 insMind，地址从 A0_config.config 读取。
"""
import sys
import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# ── 将万象AI-2改 源码加入路径 ──────────────────────────────────────────
WANXIANG_2_SRC = r"E:\万象AI-2改\src"
if WANXIANG_2_SRC not in sys.path:
    sys.path.insert(0, WANXIANG_2_SRC)

# ── 导入万象AI-2改 的配置模块 ──────────────────────────────────────────
from 任务运行文件 import A0_config

router = APIRouter(prefix="/api/video", tags=["video"])

# ── insMind 默认地址 ──────────────────────────────────────────────────
DEFAULT_INSMIND_URL = "http://localhost:8766"


# ── 请求/响应模型 ────────────────────────────────────────────────────────
class VideoGenerateRequest(BaseModel):
    prompt: str = Field(..., description="生成视频的提示词")
    model: str = Field(default="insMind", description="模型名称（当前硬编码为 insMind）")


class VideoGenerateResponse(BaseModel):
    success: bool = Field(..., description="是否生成成功")
    video_url: str = Field(default="", description="生成的视频 URL")
    error: str = Field(default="", description="错误信息（失败时）")
    model: str = Field(default="insMind", description="实际使用的模型")


def _get_insmind_url() -> str:
    """从配置中读取 insMind 服务地址"""
    return (
        A0_config.config.get("接口地址")
        or A0_config.config.get("other接口地址")
        or DEFAULT_INSMIND_URL
    )


# ── 路由 ─────────────────────────────────────────────────────────────────
@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(req: VideoGenerateRequest):
    """
    视频生成接口。

    接受提示词和模型名，调用 insMind 后端生成视频。
    当前硬编码模型为 insMind，model 参数留作扩展。

    请求示例:
        POST /api/video/generate
        {
            "prompt": "一只猫在草地上奔跑",
            "model": "insMind"
        }
    """
    insmind_url = _get_insmind_url()
    print(f"[insMind] 服务地址: {insmind_url}")
    print(f"[insMind] 提示词: {req.prompt}")

    try:
        # 调用 insMind 视频生成接口
        resp = httpx.post(
            f"{insmind_url}/api/video/generate",
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