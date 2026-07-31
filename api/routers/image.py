"""
图片生成路由

调用 PhotoGPT 后端生成图片。
地址硬编码为 localhost:8005（与 zc_backend/handlers.py 一致）。
"""
import sys
import os
import time
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/image", tags=["image"])

# PhotoGPT 地址（与 zc_backend/handlers.py 一致）
PHOTOGPT_URL = "http://localhost:8005"
POLL_INTERVAL = 3
MAX_POLL = 60


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., description="生成图片的提示词")
    model: str = Field(default="PhotoGPT", description="模型名称（当前仅支持 PhotoGPT）")


class ImageGenerateResponse(BaseModel):
    success: bool = Field(..., description="是否生成成功")
    image_url: str = Field(default="", description="生成的图片 URL")
    error: str = Field(default="", description="错误信息（失败时）")
    model: str = Field(default="PhotoGPT", description="实际使用的模型")


def _poll_job(job_id: int) -> dict:
    """轮询 PhotoGPT 任务直到完成或超时"""
    for i in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        try:
            resp = httpx.get(
                f"{PHOTOGPT_URL}/api/photogpt/generate/jobs?page=1&page_size=200",
                timeout=10,
            )
            jobs = resp.json()
            for job in jobs:
                if job.get("id") != job_id:
                    continue
                status = job.get("status", "")
                if status == "success":
                    return {"success": True, "urls": job.get("output_urls", [])}
                elif status == "failed":
                    return {
                        "success": False,
                        "error": job.get("error_message", "生成失败"),
                    }
                break
        except Exception as e:
            print(f"[PhotoGPT] 轮询异常 (第 {i+1} 次): {e}")
    return {"success": False, "error": "轮询超时"}


@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(req: ImageGenerateRequest):
    """图片生成接口"""
    print(f"[PhotoGPT] 提示词: {req.prompt}")

    try:
        resp = httpx.post(
            f"{PHOTOGPT_URL}/api/photogpt/generate",
            json={
                "prompt": req.prompt,
                "aspect_ratio": "16:9",
                "output_num": 1,
                "quality": "medium",
                "resolution": "1K",
            },
            timeout=30,
        )
        data = resp.json()

        if not data.get("success"):
            raise HTTPException(
                status_code=502,
                detail=f"PhotoGPT 提交失败: {data.get('error', '未知错误')}",
            )

        job_id = data.get("job_id")
        if not job_id:
            raise HTTPException(
                status_code=502,
                detail="PhotoGPT 返回的任务 ID 为空",
            )

        print(f"[PhotoGPT] 任务已提交, job_id={job_id}，开始轮询...")
        poll_result = _poll_job(job_id)

        if not poll_result.get("success"):
            return ImageGenerateResponse(
                success=False,
                image_url="",
                error=poll_result.get("error", "生成失败"),
                model="PhotoGPT",
            )

        urls = poll_result.get("urls", [])
        if not urls:
            return ImageGenerateResponse(
                success=False,
                image_url="",
                error="生成成功但未返回图片 URL",
                model="PhotoGPT",
            )

        return ImageGenerateResponse(
            success=True,
            image_url=urls[0],
            error="",
            model="PhotoGPT",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"图片生成失败: {str(e)}",
        )