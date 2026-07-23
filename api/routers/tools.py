"""
工具路由 — AI工具箱功能
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/list")
async def list_tools():
    """列出所有可用工具"""
    return {
        "code": 200,
        "data": {
            "tools": [
                {"id": "digital_human", "name": "AI数字人", "description": "上传视频和文案，AI自动生成数字人视频", "status": "coming_soon"},
                {"id": "vd_management", "name": "VD错峰视频管理", "description": "VD错峰任务运行数据, 异步查询同步至项目文件", "status": "coming_soon"},
                {"id": "video_download", "name": "视频下载", "description": "下载视频链接", "status": "available"},
                {"id": "subtitle_extract", "name": "字幕提取", "description": "从视频中提取字幕", "status": "available"},
                {"id": "audio_extract", "name": "音频提取", "description": "从视频中提取音频", "status": "available"},
                {"id": "video_frames", "name": "视频拆帧", "description": "将视频拆分为帧图片", "status": "available"},
                {"id": "image_merge", "name": "图片合成", "description": "将图片合成为视频", "status": "available"},
            ]
        }
    }


class ToolActionRequest(BaseModel):
    tool_id: str = Field(..., description="工具ID")
    params: dict = Field(default={}, description="工具参数")


@router.post("/execute")
async def execute_tool(req: ToolActionRequest):
    """执行工具"""
    # 工具暂未实现，返回占位
    return {
        "code": 200,
        "data": {
            "success": False,
            "message": f"工具 '{req.tool_id}' 正在开发中",
            "tool_id": req.tool_id,
        }
    }