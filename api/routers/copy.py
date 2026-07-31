"""
文案路由 — 生成/修改/保存文案 + 生成分镜
"""
import sys
import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from core.copy_tools import generate_copy, modify_copy, save_copy, load_copy, generate_storyboard

router = APIRouter(prefix="/api/copy", tags=["copy"])


class GenerateRequest(BaseModel):
    topic: str = Field(..., description="视频主题")
    tone: str = Field(default="叙事", description="语调风格")


class ModifyRequest(BaseModel):
    text: str = Field(..., description="文案内容")
    instruction: str = Field(default="", description="修改要求")


class SaveRequest(BaseModel):
    text: str = Field(..., description="文案内容")
    project_id: str = Field(default="", description="项目ID（可选）")


class StoryboardRequest(BaseModel):
    script_text: str = Field(..., description="文案内容")
    shot_count: int = Field(default=5, description="分镜数量")


@router.post("/generate")
async def api_generate_copy(req: GenerateRequest):
    """AI生成文案"""
    try:
        result = generate_copy(req.topic, req.tone)
        return {"code": 200, "data": {"reply": result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/modify")
async def api_modify_copy(req: ModifyRequest):
    """AI修改文案"""
    try:
        result = modify_copy(req.text, req.instruction)
        return {"code": 200, "data": {"reply": result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def api_save_copy(req: SaveRequest):
    """保存文案到文件"""
    try:
        result = save_copy(req.text, req.project_id)
        return {"code": 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/load")
async def api_load_copy(project_id: str = ""):
    """加载已保存的文案"""
    try:
        text = load_copy(project_id)
        return {"code": 200, "data": {"text": text}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/storyboard")
async def api_generate_storyboard(req: StoryboardRequest):
    """从文案生成分镜"""
    try:
        result = generate_storyboard(req.script_text, req.shot_count)
        return {"code": 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))