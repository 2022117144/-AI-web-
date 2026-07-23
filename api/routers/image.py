"""
图片生成路由

直接调用万象AI-2改 的 PhotoGPT 图片生成接口。
硬编码模型为 PhotoGPT，地址从 A0_config.config 读取。
"""
import sys
import os
import time
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# ── 将万象AI-2改 源码加入路径 ──────────────────────────────────────────
WANXIANG_2_SRC = r"E:\万象AI-2改\src"
if WANXIANG_2_SRC not in sys.path:
    sys.path.insert(0, WANXIANG_2_SRC)

# ── 导入万象AI-2改 的配置模块 ──────────────────────────────────────────
router = APIRouter(prefix="/api/image", tags=["image"])

# ── PhotoGPT 默认地址 ──────────────────────────────────────────────────
DEFAULT_PHOTOGPT_URL = "http://localhost:8005"
POLL_INTERVAL = 3
MAX_POLL = 60


# ── 请求/响应模型 ────────────────────────────────────────────────────────
class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., description="生成图片的提示词")
    model: str = Field(default="PhotoGPT", description="模型名称（当前仅支持 PhotoGPT）")


class ImageGenerateResponse(BaseModel):
    success: bool = Field(..., description="是否生成成功")
    image_url: str = Field(default="", description="生成的图片 URL")
    error: str = Field(default="", description="错误信息（失败时）")
    model: str = Field(default="PhotoGPT", description="实际使用的模型")


def _get_photogpt_url() -> str:
    """从配置中读取 PhotoGPT 服务地址"""
    # 延迟加载 A0_config
    from 任务运行文件 import A0_config
    # 优先使用 接口地址，其次 other接口地址，最后默认值
    return (
        A0_config.config.get("接口地址")
        or A0_config.config.get("other接口地址")
        or DEFAULT_PHOTOGPT_URL
    )


def _poll_job(photogpt_url: str, job_id: int) -> dict:
    """轮询 PhotoGPT 任务直到完成或超时"""
    for i in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        try:
            resp = httpx.get(
                f"{photogpt_url}/api/photogpt/generate/jobs?page=1&page_size=200",
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


# ── 路由 ─────────────────────────────────────────────────────────────────
@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(req: ImageGenerateRequest):
    """
    图片生成接口。

    接受提示词和模型名，调用 PhotoGPT 后端生成图片。
    当前硬编码模型为 PhotoGPT，model 参数留作扩展。

    请求示例:
        POST /api/image/generate
        {
            "prompt": "一只可爱的猫，赛博朋克风格",
            "model": "PhotoGPT"
        }
    """
    photogpt_url = _get_photogpt_url()
    print(f"[PhotoGPT] 服务地址: {photogpt_url}")
    print(f"[PhotoGPT] 提示词: {req.prompt}")

    try:
        # 提交图片生成任务
        resp = httpx.post(
            f"{photogpt_url}/api/photogpt/generate",
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

        # 轮询等待结果
        poll_result = _poll_job(photogpt_url, job_id)

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