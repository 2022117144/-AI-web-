"""
LLM 推理路由

直接调用 万象AI-2改 的 LLM 推理函数（A2_网络请求.py）。
支持通过配置自定义接口地址和 API Key。
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# ── 将 万象AI-2改 源码加入路径 ──────────────────────────────────────────
WANXIANG_2_SRC = r"E:\万象AI-2改\src"
if WANXIANG_2_SRC not in sys.path:
    sys.path.insert(0, WANXIANG_2_SRC)

# ── 导入 万象AI-2改 的 LLM 推理模块 ────────────────────────────────────
from 任务运行文件.A2_网络请求 import 网络请求
from 任务运行文件 import A0_config

router = APIRouter(prefix="/api/llm", tags=["llm"])


# ── 请求/响应模型 ────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    messages: str = Field(..., description="用户消息/提示词")
    model: str = Field(default="", description="模型名称（留空则使用配置中的 ChatGPT版本）")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="LLM 回复内容")
    model: str = Field(default="", description="实际使用的模型")
    provider: str = Field(default="", description="实际使用的后端")


# ── 模拟信号对象（API 调用不需要 UI 弹窗） ──────────────────────────────
class _MockSignal:
    """替换 PyQt5 的 signal，使其在 API 上下文中不报错"""

    @staticmethod
    def emit(data):
        pass  # API 环境不需要弹窗


class _MockMod:
    """替换 PyQt5 的 mod 对象，提供 _signal 接口"""

    def __init__(self):
        self._signal = _MockSignal()


# ── 路由 ─────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    LLM 推理接口。

    接受用户消息和可选模型名，通过 万象AI-2改 的推理引擎
    （网络请求.Close_API2D）返回结果。

    后端选择和 API Key 全部从 A0_config.config 读取：
      - ChatGPT端口 → 后端类型（通义千问/豆包/其他平台/GPT官网/本地等）
      - ChatGPT版本 → 默认模型
      - 接口地址 / other接口地址 → 自定义 API 地址
      - GPT_Token / other_key / doubao_key / tongyi_key → 对应 Key
    """
    try:
        # 选择模型：请求显式指定则覆盖配置中的默认值
        if req.model:
            A0_config.config["ChatGPT版本"] = req.model

        # 构造推理请求对象
        mod = _MockMod()
        infer = 网络请求(
            mood=None,
            请求内容=req.messages,
            任务="推理",
            mod=mod,
        )

        # 执行推理
        reply = infer.Close_API2D(stream=False)

        if reply is None:
            raise HTTPException(
                status_code=502,
                detail="LLM 推理返回空结果，请检查 API Key 和网络连接",
            )

        return ChatResponse(
            reply=reply,
            model=A0_config.config.get("ChatGPT版本", req.model or ""),
            provider=A0_config.config.get("ChatGPT端口", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM 推理失败: {str(e)}",
        )