"""
LLM 推理路由

调用 zc_backend/llm.py 的 call_llm 进行推理。
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from zc_backend import llm as llm_mod

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ChatRequest(BaseModel):
    messages: str = Field(..., description="用户消息/提示词")
    model: str = Field(default="", description="模型名称（留空则使用配置中的默认值）")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="LLM 回复内容")
    model: str = Field(default="", description="实际使用的模型")


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    LLM 推理接口。

    调用 zc_backend/llm.py 的 call_llm 进行推理。
    使用配置中的 base_url 和 API Key。
    """
    try:
        config = llm_mod.get_config()
        model = req.model or config.get("model", "")

        result = llm_mod.call_llm(
            messages=[{"role": "user", "content": req.messages}],
            model=model,
            temperature=0.7,
            max_tokens=2048,
        )

        if result is None:
            raise HTTPException(
                status_code=502,
                detail="LLM 推理返回空结果，请检查 API Key 和网络连接",
            )

        return ChatResponse(
            reply=result,
            model=model or config.get("model", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM 推理失败: {str(e)}",
        )